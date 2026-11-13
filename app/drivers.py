"""Espace livreurs du restaurant — suivi des courses, hors Uber Direct."""

import json
import re
from datetime import datetime, time, timezone
from urllib.parse import quote

from app.auth import iso, utc_now
from app.money import format_eur
from app.orders import STATUS_LABELS, place_label, set_status, when_label
from app.schedule import PARIS, now_paris
from app.ui import BTN, BTN_GHOST, FIELD, H1, INPUT, MUTED, NOTICE, esc, hidden

PHONE_RE = re.compile(r"[^\d+]")


def ensure_driver_columns(conn):
    columns = {row[1] for row in conn.execute("PRAGMA table_info(orders)")}
    for name, kind in (
        ("driver_name", "TEXT"),
        ("driver_phone", "TEXT"),
        ("driver_accepted_at", "TEXT"),
    ):
        if name not in columns:
            conn.execute(f"ALTER TABLE orders ADD COLUMN {name} {kind}")


def _today_start():
    return datetime.combine(now_paris().date(), time.min, tzinfo=PARIS).astimezone(timezone.utc)


def _paid_ok(order):
    if order["payment_method"] == "stripe" and order["payment_status"] != "paid":
        return False
    return True


def _address(order):
    return place_label(order)


def _maps_url(order):
    address = _address(order)
    if not address:
        return ""
    return "https://www.google.com/maps/dir/?api=1&destination=" + quote(address)


def _tel_href(phone):
    clean = PHONE_RE.sub("", phone or "")
    return f"tel:{clean}" if clean else ""


def _uber_handled(order):
    return bool((order["uber_delivery_id"] or "").strip())


def board(conn):
    ensure_driver_columns(conn)
    open_rows = conn.execute(
        """
        SELECT o.*, s.slot_date, s.start_time, s.end_time, z.name AS zone_name
        FROM orders o
        LEFT JOIN pickup_slots s ON s.id = o.slot_id
        LEFT JOIN delivery_zones z ON z.id = o.zone_id
        WHERE o.mode = 'delivery'
          AND o.status IN ('ready', 'out_for_delivery', 'preparing', 'accepted')
        ORDER BY o.created_at, o.id
        """
    ).fetchall()
    waiting = []
    active = []
    for order in open_rows:
        if not _paid_ok(order):
            continue
        if _uber_handled(order):
            continue
        if order["status"] == "out_for_delivery" or (order["driver_name"] or "").strip():
            if order["status"] != "completed":
                active.append(order)
        elif order["status"] in {"ready", "preparing", "accepted"}:
            waiting.append(order)

    done = conn.execute(
        """
        SELECT o.*, s.slot_date, s.start_time, s.end_time, z.name AS zone_name
        FROM orders o
        LEFT JOIN pickup_slots s ON s.id = o.slot_id
        LEFT JOIN delivery_zones z ON z.id = o.zone_id
        WHERE o.mode = 'delivery'
          AND o.status = 'completed'
          AND o.created_at >= ?
          AND IFNULL(o.driver_name, '') != ''
        ORDER BY o.id DESC
        LIMIT 20
        """,
        (iso(_today_start()),),
    ).fetchall()

    uber = conn.execute(
        """
        SELECT o.*, s.slot_date, s.start_time, s.end_time, z.name AS zone_name
        FROM orders o
        LEFT JOIN pickup_slots s ON s.id = o.slot_id
        LEFT JOIN delivery_zones z ON z.id = o.zone_id
        WHERE o.mode = 'delivery'
          AND IFNULL(o.uber_delivery_id, '') != ''
          AND o.status NOT IN ('completed', 'cancelled')
        ORDER BY o.created_at, o.id
        """
    ).fetchall()

    return {"waiting": waiting, "active": active, "done": done, "uber": uber}


def accept_order(conn, order_id, driver_name, driver_phone=""):
    ensure_driver_columns(conn)
    name = " ".join(str(driver_name or "").split())[:80]
    phone = " ".join(str(driver_phone or "").split())[:40]
    if len(name) < 2:
        return "Indiquez le nom du livreur."
    order = conn.execute("SELECT * FROM orders WHERE id = ?", (order_id,)).fetchone()
    if not order or order["mode"] != "delivery":
        return "Commande de livraison introuvable."
    if not _paid_ok(order):
        return "Cette commande n'est pas encore encaissée."
    if _uber_handled(order):
        return "Cette course est déjà chez Uber Direct."
    if order["status"] in {"cancelled", "completed"}:
        return "Cette commande n'est plus disponible."
    if (order["driver_name"] or "").strip() and order["status"] == "out_for_delivery":
        return "Un livreur a déjà pris cette course."
    if order["status"] not in {"ready", "preparing", "accepted", "out_for_delivery"}:
        return "La commande n'est pas encore prête à partir."
    now = iso(utc_now())
    conn.execute(
        """
        UPDATE orders
        SET driver_name = ?, driver_phone = ?, driver_accepted_at = ?
        WHERE id = ?
        """,
        (name, phone, now, order_id),
    )
    error = set_status(conn, order_id, "out_for_delivery")
    if error:
        return error
    conn.execute(
        "INSERT INTO order_events (order_id, status, created_at) VALUES (?, 'driver_accepted', ?)",
        (order_id, now),
    )
    return None


def complete_order(conn, order_id):
    ensure_driver_columns(conn)
    order = conn.execute("SELECT * FROM orders WHERE id = ?", (order_id,)).fetchone()
    if not order or order["mode"] != "delivery":
        return "Commande de livraison introuvable."
    if not (order["driver_name"] or "").strip():
        return "Acceptez d'abord la course."
    return set_status(conn, order_id, "completed")


def release_order(conn, order_id):
    ensure_driver_columns(conn)
    order = conn.execute("SELECT * FROM orders WHERE id = ?", (order_id,)).fetchone()
    if not order or order["mode"] != "delivery":
        return "Commande de livraison introuvable."
    if order["status"] == "completed":
        return "Cette course est déjà terminée."
    conn.execute(
        """
        UPDATE orders
        SET driver_name = NULL, driver_phone = NULL, driver_accepted_at = NULL
        WHERE id = ?
        """,
        (order_id,),
    )
    if order["status"] == "out_for_delivery":
        return set_status(conn, order_id, "ready")
    return None


def _lines(order):
    try:
        rows = json.loads(order["snapshot_json"] or "[]")
    except json.JSONDecodeError:
        rows = []
    return "".join(
        f'<li class="border-b border-line/70 py-1 text-sm">{esc(line.get("quantity"))} × {esc(line.get("name"))}</li>'
        for line in rows
    )


def _card(order, csrf, kind, default_driver="", default_phone=""):
    address = _address(order) or "Adresse manquante"
    maps = _maps_url(order)
    tel = _tel_href(order["phone"])
    status = STATUS_LABELS.get(order["status"], order["status"])
    fee = format_eur(order["delivery_fee_cents"])
    actions = []
    if kind == "waiting":
        actions.append(
            f"""
            <form class="mt-4 space-y-3" method="post" action="/admin/livreurs/{order['id']}/accepter">
              {hidden('csrf', csrf)}
              <label class="{FIELD}"><span>Nom du livreur</span>
                <input class="{INPUT}" name="livreur" required maxlength="80" value="{esc(default_driver)}" autocomplete="name">
              </label>
              <label class="{FIELD}"><span>Téléphone livreur (facultatif)</span>
                <input class="{INPUT}" name="telephone" maxlength="40" value="{esc(default_phone)}" autocomplete="tel">
              </label>
              <button class="{BTN}" type="submit">Accepter la course</button>
            </form>
            """
        )
    elif kind == "active":
        actions.append(
            f"""
            <form class="mt-4" method="post" action="/admin/livreurs/{order['id']}/livree">
              {hidden('csrf', csrf)}
              <button class="{BTN}" type="submit">Marquer livrée</button>
            </form>
            <form class="mt-2" method="post" action="/admin/livreurs/{order['id']}/relacher">
              {hidden('csrf', csrf)}
              <button class="{BTN_GHOST}" type="submit">Remettre en attente</button>
            </form>
            """
        )
    call = (
        f'<a class="{BTN_GHOST}" href="{esc(tel)}">Appeler le client</a>'
        if tel
        else f'<span class="text-sm text-ink-soft">Téléphone client manquant</span>'
    )
    itineraire = (
        f'<a class="{BTN_GHOST}" href="{esc(maps)}" target="_blank" rel="noopener noreferrer">Itinéraire</a>'
        if maps
        else ""
    )
    driver = ""
    if (order["driver_name"] or "").strip():
        driver = f'<p class="mt-2 text-sm">Livreur : <strong>{esc(order["driver_name"])}</strong></p>'
    return f"""
      <article class="border border-line bg-cream p-4">
        <div class="flex flex-wrap items-start justify-between gap-2">
          <div>
            <p class="text-xs uppercase tracking-[0.14em] text-terracotta">{esc(status)}</p>
            <h3 class="mt-1 font-display text-2xl leading-none">{esc(order["public_ref"])}</h3>
            <p class="mt-2 text-sm font-medium">{esc(order["customer_name"])}</p>
          </div>
          <p class="text-sm tabular-nums">{esc(format_eur(order["total_cents"]))}</p>
        </div>
        <p class="mt-3 text-sm leading-relaxed">{esc(when_label(order))}</p>
        <p class="mt-1 text-sm leading-relaxed">{esc(address)}</p>
        <p class="mt-1 text-sm text-ink-soft">Frais de livraison : {esc(fee)}</p>
        {driver}
        <ul class="mt-3">{_lines(order)}</ul>
        <div class="mt-4 flex flex-wrap gap-2">{call}{itineraire}</div>
        {"".join(actions)}
      </article>
    """


def _column(title, rows, csrf, kind, empty, default_driver="", default_phone=""):
    cards = "".join(_card(order, csrf, kind, default_driver, default_phone) for order in rows) or (
        f'<p class="text-sm text-ink-soft">{esc(empty)}</p>'
    )
    return f"""
      <section>
        <h2 class="font-display text-2xl">{esc(title)} <span class="text-base text-ink-soft">({len(rows)})</span></h2>
        <div class="mt-4 space-y-4">{cards}</div>
      </section>
    """


def render_board(ctx, message=""):
    ensure_driver_columns(ctx.conn)
    data = board(ctx.conn)
    is_driver = bool(ctx.user and ctx.user["role"] == "driver")
    default_driver = (ctx.user["name"] if ctx.user else "") or ""
    default_phone = (ctx.user["phone"] if ctx.user and ctx.user["role"] == "driver" else "") or ""
    notice = f'<p class="mt-4 {NOTICE}" role="status">{esc(message)}</p>' if message else ""
    uber_rows = []
    for order in data["uber"]:
        track = order["uber_tracking_url"] or ""
        link = (
            f'<a class="underline" href="{esc(track)}" target="_blank" rel="noopener noreferrer">Suivi Uber</a>'
            if track
            else esc(order["uber_status"] or "Uber Direct")
        )
        uber_rows.append(
            f'<li class="border-b border-line py-3 text-sm"><strong>{esc(order["public_ref"])}</strong> — {esc(order["customer_name"])} — {link}</li>'
        )
    uber_block = ""
    if uber_rows and not is_driver:
        uber_block = f"""
        <section class="mt-10 border border-line bg-paper-2 p-5">
          <h2 class="font-display text-2xl">Uber Direct</h2>
          <p class="mt-2 {MUTED}">Courses confiées à Uber — visibles ici pour le suivi, sans action livreur restaurant.</p>
          <ul class="mt-4">{"".join(uber_rows)}</ul>
        </section>
        """
    title = "Mes courses" if is_driver else "Livreurs"
    intro = (
        "Vos livraisons du restaurant : accepter une course, appeler le client, ouvrir l'itinéraire, marquer livrée."
        if is_driver
        else "Suivi des livraisons assurées par le restaurant : accepter une course, appeler le client, ouvrir l'itinéraire, marquer livrée."
    )
    body = f"""
      <div class="flex flex-wrap items-end justify-between gap-4">
        <div>
          <h1 class="{H1}">{esc(title)}</h1>
          <p class="mt-3 max-w-2xl text-sm leading-relaxed text-ink-soft">{esc(intro)}</p>
        </div>
        <a class="{BTN_GHOST}" href="/admin/livreurs">Actualiser</a>
      </div>
      {notice}
      <div class="mt-8 grid gap-8 lg:grid-cols-3">
        {_column("À prendre", data["waiting"], ctx.session["csrf"], "waiting", "Aucune course à prendre.", default_driver, default_phone)}
        {_column("En cours", data["active"], ctx.session["csrf"], "active", "Aucune course en cours.")}
        {_column("Livrées aujourd'hui", data["done"], ctx.session["csrf"], "done", "Aucune livraison terminée pour l'instant.")}
      </div>
      {uber_block}
      <script>
        setTimeout(function () {{
          if (document.visibilityState === "visible") window.location.reload();
        }}, 20000);
      </script>
    """
    return body
