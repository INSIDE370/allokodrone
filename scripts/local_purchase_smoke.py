"""Smoke test local purchase path against run.py (:8080)."""

from __future__ import annotations

import json
import urllib.error
import urllib.request
import http.cookiejar

BASE = "http://127.0.0.1:8080"
jar = http.cookiejar.CookieJar()
opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(jar))
results: list[tuple[str, bool, str]] = []


def check(name: str, ok: bool, detail: str = "") -> None:
    results.append((name, bool(ok), detail))
    print(("OK   " if ok else "FAIL "), name, detail)


def call(method: str, path: str, body=None, headers=None):
    hdrs = {"Accept": "application/json", "User-Agent": "AllocodroneLocalSmoke/1.0"}
    if headers:
        hdrs.update(headers)
    data = None
    if body is not None:
        data = json.dumps(body).encode("utf-8")
        hdrs["Content-Type"] = "application/json"
    req = urllib.request.Request(BASE + path, data=data, headers=hdrs, method=method)
    try:
        with opener.open(req, timeout=45) as res:
            raw = res.read()
            ctype = res.headers.get("Content-Type", "")
            payload = json.loads(raw.decode("utf-8")) if "json" in ctype else raw[:300]
            return res.status, payload
    except urllib.error.HTTPError as exc:
        raw = exc.read()
        try:
            payload = json.loads(raw.decode("utf-8"))
        except Exception:
            payload = raw[:300].decode("utf-8", "replace")
        return exc.code, payload


st, sess = call("GET", "/api/session")
csrf = sess.get("csrf") if isinstance(sess, dict) else ""
slots = sess.get("slots") if isinstance(sess, dict) else []
check(
    "GET /api/session",
    st == 200 and bool(csrf),
    f"status={st} csrf={bool(csrf)} slots={len(slots) if isinstance(slots, list) else 0}",
)

st, home = call("GET", "/api/accueil")
feat = home.get("featured") if isinstance(home, dict) else []
check("GET /api/accueil", st == 200 and bool(feat), f"status={st} featured={len(feat or [])}")

prod = None
for item in feat or []:
    if item.get("orderable") and item.get("priceConfirmed") and not item.get("hasOptions"):
        prod = item
        break
if not prod:
    for item in feat or []:
        if item.get("id"):
            prod = item
            break
pid = prod.get("id") if prod else None
check("produit", bool(pid), f"id={pid} name={(prod or {}).get('name')}")

st, added = call(
    "POST",
    "/api/panier/ajouter",
    {"produit": pid, "quantite": 1, "choix": [], "notes": ""},
    {"X-CSRF": csrf},
)
if st == 400:
    st, sess = call("GET", "/api/session")
    csrf = sess.get("csrf") if isinstance(sess, dict) else csrf
    st, added = call(
        "POST",
        "/api/panier/ajouter",
        {"produit": pid, "quantite": 1, "choix": [], "notes": ""},
        {"X-CSRF": csrf},
    )
check("POST /api/panier/ajouter", st < 400, f"status={st} body={str(added)[:200]}")

st, panier = call("GET", "/api/panier")
lines = []
if isinstance(panier, dict):
    lines = panier.get("lines") or panier.get("items") or (panier.get("cart") or {}).get("lines") or []
check("panier non vide", st == 200 and len(lines) > 0, f"status={st} lines={len(lines)}")

st, checkout = call("GET", "/api/commander")
check(
    "GET /api/commander",
    st == 200 and isinstance(checkout, dict),
    f"status={st} keys={list(checkout)[:12] if isinstance(checkout, dict) else checkout}",
)

slot_id = ""
if isinstance(checkout, dict) and checkout.get("slots"):
    slot_id = str(checkout["slots"][0]["id"])
elif slots:
    slot_id = str(slots[0]["id"])

methods = []
if isinstance(checkout, dict):
    methods = checkout.get("paymentMethods") or checkout.get("methods") or checkout.get("payments") or []
codes = []
for item in methods:
    code = item.get("code") if isinstance(item, dict) else item
    if code:
        codes.append(str(code))
# Click & Collect exige la carte
method = "stripe" if "stripe" in codes else (codes[0] if codes else "stripe")
check("paiement disponible", bool(codes), f"methods={codes} stripeReady={checkout.get('stripeReady') if isinstance(checkout, dict) else None}")

order_body = {
    "idempotencyKey": "local-smoke-order-2",
    "nom": "Test Local",
    "email": "test@example.com",
    "telephone": "0612345678",
    "mode": "pickup",
    "slotId": slot_id,
    "paiement": method,
    "conditions": True,
}
st, order = call("POST", "/api/commander", order_body, headers={"X-CSRF": csrf})
if st == 400:
    st, sess = call("GET", "/api/session")
    csrf = sess.get("csrf") if isinstance(sess, dict) else csrf
    st, order = call("POST", "/api/commander", order_body, headers={"X-CSRF": csrf})
ok_order = st == 200 and isinstance(order, dict) and (
    order.get("ok") or order.get("ref") or order.get("checkoutUrl") or order.get("url")
)
check("POST /api/commander", ok_order, f"status={st} body={str(order)[:280]}")

ref = order.get("ref") if isinstance(order, dict) else None
checkout_url = None
if isinstance(order, dict):
    checkout_url = order.get("checkoutUrl") or order.get("url")
if checkout_url:
    check("stripe checkout url", str(checkout_url).startswith("http"), f"url={str(checkout_url)[:120]}")
if ref:
    st, conf = call("GET", f"/api/commande/{ref}")
    check(f"GET /api/commande/{ref}", st == 200, f"status={st} body={str(conf)[:180]}")

fails = [item for item in results if not item[1]]
print("\n=== SUMMARY ===")
print(f"passed={len(results) - len(fails)} failed={len(fails)} total={len(results)}")
for name, _ok, detail in fails:
    print("FAIL:", name, "|", detail)
