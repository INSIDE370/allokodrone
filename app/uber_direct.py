"""Uber Direct. Aucun appel tant que les accès officiels ne sont pas configurés."""

import hashlib
import hmac
import json
import os
import urllib.parse
import urllib.request

AUTH_URL = "https://auth.uber.com/oauth/v2/token"
API = "https://api.uber.com"


def configured():
    return all(
        os.environ.get(name, "").strip()
        for name in ("UBER_CLIENT_ID", "UBER_CLIENT_SECRET", "UBER_CUSTOMER_ID", "ALLOKO_RESTAURANT_PHONE")
    )


def _secret():
    return os.environ.get("UBER_CLIENT_SECRET", "").strip()


def _customer():
    return urllib.parse.quote(os.environ.get("UBER_CUSTOMER_ID", "").strip(), safe="")


def verify_signature(payload, header):
    secret = _secret()
    if not secret or not header:
        return False
    expected = hmac.new(secret.encode("utf-8"), payload, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, header.strip())


def _token():
    fields = urllib.parse.urlencode(
        {
            "client_id": os.environ["UBER_CLIENT_ID"].strip(),
            "client_secret": _secret(),
            "grant_type": "client_credentials",
            "scope": "eats.deliveries",
        }
    ).encode("utf-8")
    request = urllib.request.Request(
        AUTH_URL,
        data=fields,
        method="POST",
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )
    try:
        with urllib.request.urlopen(request, timeout=20) as response:
            data = json.loads(response.read().decode("utf-8"))
    except Exception:
        return None, "Uber Direct est injoignable."
    token = data.get("access_token")
    if not token:
        return None, "Uber Direct n'a pas fourni d'accès."
    return token, None


def _json(method, path, token, payload=None):
    body = None if payload is None else json.dumps(payload).encode("utf-8")
    request = urllib.request.Request(API + path, data=body, method=method)
    request.add_header("Authorization", "Bearer " + token)
    request.add_header("Content-Type", "application/json")
    try:
        with urllib.request.urlopen(request, timeout=20) as response:
            raw = response.read().decode("utf-8")
            return (json.loads(raw) if raw else {}), None
    except Exception:
        return None, "Uber Direct a refusé la demande."


def _address(street, postcode, city):
    return json.dumps(
        {
            "street_address": [street],
            "city": city,
            "zip_code": postcode,
            "country": "FR",
        },
        ensure_ascii=False,
    )


def dispatch_order(conn, order):
    if not configured():
        return "Uber Direct n'est pas configuré. La livraison reste assurée par le restaurant."
    if order["mode"] != "delivery" or order["status"] in {"cancelled", "completed"}:
        return "Cette commande ne peut pas être transmise à Uber Direct."
    if order["uber_delivery_id"]:
        return None
    try:
        address = json.loads(order["address_json"] or "{}")
    except json.JSONDecodeError:
        return "Adresse de livraison illisible."
    lines = json.loads(order["snapshot_json"])
    token, error = _token()
    if error:
        return error
    payload = {
        "pickup_name": "ALLOKODRONE",
        "pickup_address": _address("24 rue Emmanuel Arago", "93130", "Noisy-le-Sec"),
        "pickup_phone_number": os.environ["ALLOKO_RESTAURANT_PHONE"].strip(),
        "dropoff_name": order["customer_name"],
        "dropoff_address": _address(address.get("rue") or "", address.get("code_postal") or "", address.get("ville") or ""),
        "dropoff_phone_number": order["phone"],
        "manifest_items": [
            {"name": line["name"], "quantity": int(line["quantity"]), "size": "small", "price": int(line["line_cents"])}
            for line in lines
        ],
        "external_id": order["public_ref"],
    }
    if os.environ.get("UBER_SANDBOX", "").strip() == "1":
        payload["test_specifications"] = {"robo_courier_specification": {"mode": "auto"}}
    data, error = _json("POST", f"/v1/customers/{_customer()}/deliveries", token, payload)
    if error or not data or not data.get("id"):
        return error or "Uber Direct n'a pas créé de livraison."
    conn.execute(
        """
        UPDATE orders
        SET uber_delivery_id = ?, uber_status = ?, uber_tracking_url = ?
        WHERE id = ?
        """,
        (data.get("id"), data.get("status") or "pending", data.get("tracking_url") or "", order["id"]),
    )
    return None


def handle_webhook(conn, payload, signature):
    if not _secret():
        return 503, {"ok": False, "error": "Uber Direct n'est pas configuré."}
    if not verify_signature(payload, signature):
        return 400, {"ok": False, "error": "Signature invalide."}
    try:
        event = json.loads(payload.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        return 400, {"ok": False, "error": "Notification illisible."}
    data = event.get("data") or event
    delivery_id = data.get("delivery_id") or data.get("id") or ""
    status = data.get("status") or ""
    if not delivery_id:
        return 200, {"ok": True, "ignored": True}
    order = conn.execute("SELECT id FROM orders WHERE uber_delivery_id = ?", (delivery_id,)).fetchone()
    if not order:
        return 200, {"ok": True, "ignored": True}
    conn.execute("UPDATE orders SET uber_status = ? WHERE id = ?", (status, order["id"]))
    return 200, {"ok": True}
