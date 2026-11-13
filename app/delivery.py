"""Livraison par zone ou par distance. Les frais viennent toujours de la base."""

import json
import os
import urllib.error
import urllib.parse
import urllib.request

from app.schedule import load_json_setting

ORIGIN = "24 rue Emmanuel Arago, 93130 Noisy-le-Sec, France"
ORS = "https://api.openrouteservice.org"
_transport = None


def delivery_mode(conn):
    value = load_json_setting(conn, "delivery_mode", "zones")
    return value if value in {"zones", "distance"} else "zones"


def geo_key(conn=None):
    provider = os.environ.get("GEO_PROVIDER", "").strip()
    env_key = os.environ.get("GEO_API_KEY", "").strip()
    if provider == "openrouteservice" and env_key:
        return env_key
    if conn is None:
        return ""
    stored = load_json_setting(conn, "geo_api_key", "")
    return stored.strip() if isinstance(stored, str) else ""


def geo_configured(conn=None):
    return bool(geo_key(conn))


def customer_delivery_open(conn):
    if delivery_mode(conn) == "distance":
        return bool(active_bands(conn)) and geo_configured(conn)
    row = conn.execute(
        """
        SELECT COUNT(*) AS n FROM delivery_zones
        WHERE active = 1 AND fee_confirmed = 1 AND fee_cents IS NOT NULL
        """
    ).fetchone()
    return bool(row["n"])


def active_bands(conn):
    return conn.execute(
        """
        SELECT * FROM distance_bands
        WHERE active = 1 AND fee_confirmed = 1 AND fee_cents IS NOT NULL
        ORDER BY max_meters
        """
    ).fetchall()


def quote_delivery(conn, address, transport=None):
    if delivery_mode(conn) != "distance":
        return None, "La livraison à la distance n'est pas le mode actif."
    bands = active_bands(conn)
    if not bands:
        return None, "Aucun barème de distance n'est validé."
    chosen = transport if transport is not None else _transport
    if chosen is None and not geo_configured(conn):
        return None, "Le calcul de distance n'est pas configuré."
    meters, error = _meters(address, chosen, geo_key(conn))
    if error:
        return None, error
    fee, error = fee_for_meters(conn, meters)
    if error:
        return None, error
    return {"fee_cents": fee, "meters": int(meters)}, None


def fee_for_km(conn, raw):
    text = str(raw or "").strip().replace(",", ".")
    try:
        km = float(text)
    except ValueError:
        return None, "Distance invalide."
    if km <= 0 or km > 100:
        return None, "Distance invalide."
    return fee_for_meters(conn, int(round(km * 1000)))


def fee_for_meters(conn, meters):
    bands = active_bands(conn)
    if not bands:
        return None, "Aucun palier ouvert."
    band = next((item for item in bands if int(meters) <= int(item["max_meters"])), None)
    if not band:
        last = int(bands[-1]["max_meters"]) / 1000
        return None, f"Hors des prix ouverts : le dernier palier s'arrête à {last:g} km. Ajoutez un palier plus long, avec son montant."
    return int(band["fee_cents"]), None


def probe_key(key):
    _origin, error = _geocode(key, ORIGIN)
    return error


def _meters(address, transport, key=""):
    if transport is not None:
        return transport(address)
    key = (key or "").strip()
    if not key:
        return None, "Le calcul de distance n'est pas configuré."
    destination = ", ".join(
        part for part in (address.get("rue"), address.get("code_postal"), address.get("ville"), "France") if part
    )
    origin, error = _geocode(key, ORIGIN)
    if error:
        return None, error
    target, error = _geocode(key, destination)
    if error:
        return None, "Cette adresse est introuvable."
    payload = json.dumps({"coordinates": [origin, target]}).encode("utf-8")
    request = urllib.request.Request(
        ORS + "/v2/directions/driving-car",
        data=payload,
        method="POST",
        headers={"Authorization": key, "Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(request, timeout=20) as response:
            data = json.loads(response.read().decode("utf-8"))
    except Exception:
        return None, "Le service de distance est injoignable."
    try:
        meters = data["routes"][0]["summary"]["distance"]
    except (KeyError, IndexError, TypeError):
        return None, "La distance n'a pas pu être calculée."
    return int(round(float(meters))), None


def meters_from_coords(conn, latitude, longitude, transport=None):
    try:
        lat = float(latitude)
        lon = float(longitude)
    except (TypeError, ValueError):
        return None, "La position est invalide."
    if not (-90 <= lat <= 90 and -180 <= lon <= 180):
        return None, "La position est invalide."
    if transport is not None:
        return transport({"lat": lat, "lon": lon})
    key = geo_key(conn)
    if not key:
        return None, "Le calcul de distance n'est pas configuré."
    origin, error = _geocode(key, ORIGIN)
    if error:
        return None, error
    payload = json.dumps({"coordinates": [origin, [lon, lat]]}).encode("utf-8")
    request = urllib.request.Request(
        ORS + "/v2/directions/driving-car",
        data=payload,
        method="POST",
        headers={"Authorization": key, "Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(request, timeout=20) as response:
            data = json.loads(response.read().decode("utf-8"))
        meters = data["routes"][0]["summary"]["distance"]
    except urllib.error.HTTPError as exc:
        if exc.code in {401, 403}:
            return None, "La clé OpenRouteService a été refusée."
        return None, "La distance n'a pas pu être calculée."
    except Exception:
        return None, "La distance n'a pas pu être calculée."
    return int(round(float(meters))), None


def quote_from_coords(conn, latitude, longitude, transport=None):
    if delivery_mode(conn) != "distance":
        return None, "La livraison à la distance n'est pas le mode actif."
    if not active_bands(conn):
        return None, "Aucun barème de distance n'est validé."
    meters, error = meters_from_coords(conn, latitude, longitude, transport=transport)
    if error:
        return None, error
    fee, error = fee_for_meters(conn, meters)
    if error:
        return None, error
    return {"fee_cents": fee, "meters": int(meters)}, None


def reverse_address(conn, latitude, longitude, transport=None, require_complete=True):
    try:
        lat = float(latitude)
        lon = float(longitude)
    except (TypeError, ValueError):
        return None, "La position est invalide."
    if not (-90 <= lat <= 90 and -180 <= lon <= 180):
        return None, "La position est invalide."
    if transport is not None:
        return transport(lat, lon)
    key = geo_key(conn)
    if not key:
        return None, "Le calcul de distance n'est pas configuré."
    query = urllib.parse.urlencode(
        {
            "point.lat": f"{lat:.7f}",
            "point.lon": f"{lon:.7f}",
            "size": 1,
            "boundary.country": "FR",
        }
    )
    request = urllib.request.Request(
        ORS + "/geocode/reverse?" + query,
        headers={"Authorization": key},
    )
    try:
        with urllib.request.urlopen(request, timeout=20) as response:
            data = json.loads(response.read().decode("utf-8"))
        props = data["features"][0]["properties"]
    except urllib.error.HTTPError as exc:
        if exc.code in {401, 403}:
            return None, "La clé OpenRouteService a été refusée."
        return None, "La position n'a pas pu être lue."
    except Exception:
        return None, "La position n'a pas pu être lue."
    street = str(props.get("street") or props.get("name") or "").strip()
    number = str(props.get("housenumber") or "").strip()
    rue = " ".join(part for part in (number, street) if part).strip()
    code_postal = str(props.get("postalcode") or "").strip()
    ville = str(
        props.get("locality")
        or props.get("localadmin")
        or props.get("county")
        or props.get("region")
        or ""
    ).strip()
    if require_complete and (not rue or not code_postal or not ville):
        return None, "Cette position ne donne pas une adresse complète."
    return {"rue": rue, "codePostal": code_postal, "ville": ville}, None


def _geocode(key, text):
    query = urllib.parse.urlencode({"text": text, "size": 1, "boundary.country": "FR"})
    request = urllib.request.Request(
        ORS + "/geocode/search?" + query,
        headers={"Authorization": key},
    )
    try:
        with urllib.request.urlopen(request, timeout=20) as response:
            data = json.loads(response.read().decode("utf-8"))
        coords = data["features"][0]["geometry"]["coordinates"]
        return [float(coords[0]), float(coords[1])], None
    except urllib.error.HTTPError as exc:
        if exc.code in {401, 403}:
            return None, "La clé OpenRouteService a été refusée."
        return None, "Le service de distance est injoignable."
    except Exception:
        return None, "Le service de distance est injoignable."
