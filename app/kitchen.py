"""Écran cuisine. Les plats, les postes et les délais viennent des données enregistrées."""

import json
from datetime import datetime, time, timezone
from urllib.parse import urlencode

from app.auth import iso
from app.orders import OPEN_STATUSES, set_status
from app.schedule import PARIS, load_json_setting, now_paris
from app.ui import esc, hidden

COLUMNS = (
    ("received", "Nouvelles"),
    ("accepted", "À préparer"),
    ("preparing", "En préparation"),
    ("ready", "Prêtes"),
    ("out_for_delivery", "En livraison"),
)
RANK = {"urgent": 0, "attention": 1, "normal": 2}
LEVEL_LABEL = {"urgent": "Urgent", "attention": "Attention", "normal": "Normal"}
MODE_LABEL = {"pickup": "Click & Collect", "delivery": "Livraison"}
HISTORY_PAGE = 20


def thresholds(conn):
    raw = load_json_setting(conn, "kitchen_thresholds", {})
    attention = _minutes(raw.get("attention_minutes") if isinstance(raw, dict) else None, 8)
    urgent = _minutes(raw.get("urgent_minutes") if isinstance(raw, dict) else None, 15)
    if urgent <= attention:
        urgent = attention + 1
    return {"attention_minutes": attention, "urgent_minutes": urgent}


def save_thresholds(conn, attention_raw, urgent_raw):
    attention = _minutes(attention_raw, None)
    urgent = _minutes(urgent_raw, None)
    if attention is None or urgent is None:
        return "Indiquez les deux délais en minutes, entre 1 et 180."
    if urgent <= attention:
        return "Le délai urgent doit être plus long que le délai d'attention."
    conn.execute(
        """
        INSERT INTO settings (key, value) VALUES ('kitchen_thresholds', ?)
        ON CONFLICT(key) DO UPDATE SET value = excluded.value
        """,
        (json.dumps({"attention_minutes": attention, "urgent_minutes": urgent}),),
    )
    return None


def needs_confirmation(form):
    return (
        form.get("retour") == "service"
        and form.get("statut") in {"completed", "cancelled"}
        and form.get("confirmer") != "1"
    )


def kitchen_return(form):
    kept = []
    for key in ("poste", "q", "mode", "heure", "vue", "page"):
        value = (form.get(key) or "").strip()
        if value:
            kept.append((key, value))
    return "/admin/cuisine" + (("?" + urlencode(kept)) if kept else "")


def save_issue(conn, order_id, text):
    order = conn.execute("SELECT id FROM orders WHERE id = ?", (order_id,)).fetchone()
    if not order:
        return "Commande introuvable."
    clean = " ".join(str(text or "").split())[:280]
    conn.execute("UPDATE orders SET kitchen_issue = ? WHERE id = ?", (clean, order_id))
    return None


def mark_line(conn, order_id, index, done, now=None):
    order = conn.execute("SELECT * FROM orders WHERE id = ?", (order_id,)).fetchone()
    if not order:
        return "Commande introuvable."
    lines = _lines(order)
    if index < 0 or index >= len(lines):
        return "Plat introuvable."
    conn.execute(
        """
        INSERT INTO kitchen_lines (order_id, line_index, done) VALUES (?, ?, ?)
        ON CONFLICT(order_id, line_index) DO UPDATE SET done = excluded.done
        """,
        (order_id, index, 1 if done else 0),
    )
    finished = _done_indexes(conn, order_id)
    complete = bool(lines) and all(position in finished for position in range(len(lines)))
    if complete and order["status"] == "preparing":
        return set_status(conn, order_id, "ready")
    if not complete and order["status"] == "ready":
        return set_status(conn, order_id, "preparing")
    return None


def mark_ready(conn, order_id, confirmed):
    if confirmed != "1":
        return "Confirmez que tous les postes ont fini."
    order = conn.execute("SELECT * FROM orders WHERE id = ?", (order_id,)).fetchone()
    if not order:
        return "Commande introuvable."
    if order["status"] not in {"accepted", "preparing", "ready"}:
        return "Acceptez la commande avant de la marquer prête."
    for index in range(len(_lines(order))):
        conn.execute(
            """
            INSERT INTO kitchen_lines (order_id, line_index, done) VALUES (?, ?, 1)
            ON CONFLICT(order_id, line_index) DO UPDATE SET done = 1
            """,
            (order_id, index),
        )
    if order["status"] == "ready":
        return None
    return set_status(conn, order_id, "ready")


def level_for(order, now, limits):
    slot_date = _field(order, "slot_date")
    start_time = _field(order, "start_time")
    if order["mode"] == "pickup" and slot_date and start_time:
        slot = datetime.fromisoformat(f"{slot_date}T{start_time}").replace(tzinfo=PARIS)
        until = (slot - now).total_seconds() / 60
        if until <= 0:
            return "urgent"
        if until <= limits["urgent_minutes"]:
            return "attention"
        return "normal"
    created = _moment(order["created_at"])
    minutes = max(0, (now - created).total_seconds() / 60)
    if minutes >= limits["urgent_minutes"]:
        return "urgent"
    if minutes >= limits["attention_minutes"]:
        return "attention"
    return "normal"


def average_prep_minutes(conn, now=None):
    now = now or now_paris()
    start = datetime.combine(now.date(), time.min, tzinfo=PARIS).astimezone(timezone.utc)
    rows = conn.execute(
        """
        SELECT o.created_at, MIN(e.created_at) AS ready_at
        FROM orders o
        JOIN order_events e ON e.order_id = o.id AND e.status IN ('ready', 'completed')
        WHERE o.created_at >= ?
        GROUP BY o.id
        """,
        (iso(start),),
    ).fetchall()
    spans = []
    for row in rows:
        created = _moment(row["created_at"])
        ready = _moment(row["ready_at"])
        if ready >= created:
            spans.append((ready - created).total_seconds() / 60)
    if not spans:
        return None
    return round(sum(spans) / len(spans))


def revision(conn):
    event = conn.execute("SELECT COALESCE(MAX(id), 0) AS n FROM order_events").fetchone()["n"]
    order = conn.execute("SELECT COALESCE(MAX(id), 0) AS n FROM orders").fetchone()["n"]
    done = conn.execute("SELECT COALESCE(SUM(done), 0) AS n FROM kitchen_lines").fetchone()["n"]
    issues = conn.execute(
        "SELECT COUNT(*) AS n FROM orders WHERE kitchen_issue IS NOT NULL AND kitchen_issue != ''"
    ).fetchone()["n"]
    limits = thresholds(conn)
    return f"{event}.{order}.{done}.{issues}.{limits['attention_minutes']}.{limits['urgent_minutes']}"


def render_kitchen(ctx, query):
    board = load_board(ctx.conn, query)
    return _page(ctx, board)


def render_fragment(ctx, query):
    board = load_board(ctx.conn, query)
    return _live(ctx, board)


def load_board(conn, query, now=None):
    now = now or now_paris()
    filters = _filters(conn, query)
    limits = thresholds(conn)
    mapping = _category_map(conn)
    orders = []
    for order in _open_orders(conn):
        data = dict(order)
        data["_categories"] = mapping
        orders.append(data)
    categories = conn.execute("SELECT slug, name FROM categories ORDER BY sort_order, name").fetchall()
    done_map = _done_map(conn, [order["id"] for order in orders])
    metrics = _metrics(orders, done_map, now, limits, conn)
    if filters["vue"] == "terminees":
        history = _history(conn, filters["page"], now)
        shown = []
    else:
        history = None
        shown = [order for order in orders if _matches(order, filters)]
    columns = []
    for status, title in COLUMNS:
        group = [order for order in shown if order["status"] == status]
        group.sort(key=lambda order: (RANK[level_for(order, now, limits)], order["created_at"], order["id"]))
        columns.append((status, title, group))
    return {
        "now": now,
        "limits": limits,
        "filters": filters,
        "categories": categories,
        "done": done_map,
        "metrics": metrics,
        "columns": columns,
        "history": history,
        "hours": _hours(orders),
        "revision": revision(conn),
        "received": sum(1 for order in orders if order["status"] == "received"),
    }


def _page(ctx, board):
    filters = board["filters"]
    stations = "".join(_station_link(filters, row) for row in board["categories"])
    hours = "".join(
        f'<option value="{hour}"{" selected" if filters["heure"] == str(hour) else ""}>{hour} h</option>'
        for hour in board["hours"]
    )
    mode_pickup = " selected" if filters["mode"] == "pickup" else ""
    mode_delivery = " selected" if filters["mode"] == "delivery" else ""
    history_on = filters["vue"] == "terminees"
    return f"""
    <div id="kds" class="-mx-4 bg-night px-4 py-6 text-cream sm:-mx-6 sm:px-6" data-poll="{esc(_poll_url(filters))}" data-revision="{esc(board['revision'])}" data-received="{board['received']}">
      <div class="flex flex-wrap items-end justify-between gap-4">
        <div>
          <p class="text-xs font-medium uppercase tracking-[0.16em] text-terracotta">Cuisine</p>
          <h1 class="mt-2 font-display text-4xl leading-none">Service en cours</h1>
        </div>
        <div class="flex flex-wrap items-center gap-2">
          <p id="kds-live" class="text-sm text-cream/80" role="status">En direct</p>
          <button class="inline-flex min-h-12 items-center border border-cream/40 px-4 text-sm" type="button" data-kds-full>Plein écran</button>
          <a class="inline-flex min-h-12 items-center border border-cream/40 px-4 text-sm" href="{esc(_link(filters, vue='' if history_on else 'terminees', page='1'))}">{'Service en cours' if history_on else "Terminées aujourd'hui"}</a>
        </div>
      </div>
      <form class="mt-5 grid gap-2 sm:grid-cols-[minmax(0,1fr)_11rem_8rem_auto]" method="get" action="/admin/cuisine">
        {hidden('poste', filters['poste'])}
        {hidden('vue', filters['vue'])}
        <label class="text-sm"><span class="mb-1 block text-cream/70">Recherche</span><input class="min-h-12 w-full border border-cream/30 bg-transparent px-3 text-cream" name="q" value="{esc(filters['q'])}" placeholder="Numéro, client ou téléphone"></label>
        <label class="text-sm"><span class="mb-1 block text-cream/70">Type</span>
          <select class="min-h-12 w-full border border-cream/30 bg-night px-3 text-cream" name="mode">
            <option value="">Tous</option>
            <option value="pickup"{mode_pickup}>Click &amp; Collect</option>
            <option value="delivery"{mode_delivery}>Livraison</option>
          </select>
        </label>
        <label class="text-sm"><span class="mb-1 block text-cream/70">Heure</span>
          <select class="min-h-12 w-full border border-cream/30 bg-night px-3 text-cream" name="heure"><option value="">Toutes</option>{hours}</select>
        </label>
        <button class="inline-flex min-h-12 items-center justify-center bg-terracotta px-4 text-sm font-medium text-cream sm:self-end" type="submit">Filtrer</button>
      </form>
      <nav class="mt-4 flex gap-2 overflow-x-auto" aria-label="Postes">
        <a class="{_chip(not filters['poste'])}" href="{esc(_link(filters, poste=''))}">Tous les postes</a>
        {stations}
      </nav>
      {_live(ctx, board)}
      <details class="mt-6 border border-cream/20 p-4">
        <summary class="cursor-pointer text-sm">Délais d'alerte</summary>
        <p class="mt-2 text-sm text-cream/70">Une livraison passe en attention, puis en urgent, selon le temps écoulé depuis la commande. Un retrait passe en attention quand le créneau approche, puis en urgent à l'heure du créneau.</p>
        <form class="mt-3 flex flex-wrap items-end gap-3" method="post" action="/admin/cuisine/delais">
          {hidden('csrf', ctx.session['csrf'])}
          {_keep(filters)}
          <label class="text-sm">Attention (minutes)<input class="mt-1 block min-h-12 w-28 border border-cream/30 bg-transparent px-3 text-cream" name="attention" inputmode="numeric" value="{board['limits']['attention_minutes']}"></label>
          <label class="text-sm">Urgent (minutes)<input class="mt-1 block min-h-12 w-28 border border-cream/30 bg-transparent px-3 text-cream" name="urgent" inputmode="numeric" value="{board['limits']['urgent_minutes']}"></label>
          <button class="inline-flex min-h-12 items-center bg-cream px-4 text-sm font-medium text-ink" type="submit">Enregistrer</button>
        </form>
      </details>
    </div>
    """


def _live(ctx, board):
    metrics = board["metrics"]
    figures = (
        ("En attente", metrics["waiting"]),
        ("En préparation", metrics["preparing"]),
        ("Urgentes", metrics["urgent"]),
        ("Prêtes", metrics["ready"]),
        ("Temps moyen", metrics["average"]),
    )
    metric_html = "".join(
        f'<li class="border border-cream/20 px-3 py-3"><p class="text-xs uppercase tracking-[0.12em] text-cream/60">{esc(label)}</p><p class="mt-1 font-display text-3xl leading-none">{esc(value)}</p></li>'
        for label, value in figures
    )
    if board["history"] is not None:
        body = _history_view(board["history"], board["filters"])
    else:
        body = _columns(ctx, board)
    return f"""
    <div id="kds-sync" data-revision="{esc(board['revision'])}" data-received="{board['received']}">
      <ul id="kds-metrics" class="mt-5 grid grid-cols-2 gap-2 lg:grid-cols-5">{metric_html}</ul>
      <div id="kds-board" class="mt-5">{body}</div>
    </div>
    """


def _columns(ctx, board):
    columns = []
    urgent_count = 0
    for status, title, group in board["columns"]:
        urgent_count += sum(1 for order in group if level_for(order, board["now"], board["limits"]) == "urgent")
        cards = "".join(_card(ctx, board, order) for order in group) or '<p class="px-1 text-sm text-cream/50">Aucune</p>'
        mark = ""
        if any(level_for(order, board["now"], board["limits"]) == "urgent" for order in group):
            mark = '<span class="text-xs font-medium uppercase tracking-[0.12em] text-terracotta">Urgent</span>'
        columns.append(
            f"""
            <section class="flex min-h-40 min-w-0 flex-col border border-cream/15 bg-night-2" data-kds-column="{esc(status)}">
              <header class="flex items-center justify-between gap-2 border-b border-cream/15 px-3 py-3">
                <h2 class="font-display text-xl leading-none">{esc(title)}</h2>
                <span class="inline-flex h-8 min-w-8 items-center justify-center bg-cream px-2 text-sm font-medium text-ink">{len(group)}</span>
              </header>
              <div class="flex items-center justify-between px-3 py-2">{mark}</div>
              <div class="max-h-[32rem] space-y-3 overflow-y-auto px-3 pb-3" data-kds-scroll>{cards}</div>
            </section>
            """
        )
    return f'<div class="grid grid-cols-1 gap-3 md:grid-cols-2 xl:grid-cols-3 2xl:grid-cols-5">{"".join(columns)}</div>'


def _card(ctx, board, order):
    limits = board["limits"]
    state = level_for(order, board["now"], limits)
    lines = _visible_lines(order, board)
    done = board["done"].get(order["id"], set())
    dishes = []
    for index, line, category in lines:
        note = str(line.get("notes") or "").strip()
        options = str(line.get("options") or "").strip()
        extra = f'<span class="mt-0.5 block text-sm text-cream/70">{esc(options)}</span>' if options else ""
        instruction = f'<span class="mt-0.5 block text-sm text-saffron">Instruction : {esc(note)}</span>' if note else ""
        station = f'<span class="mt-0.5 block text-xs uppercase tracking-[0.12em] text-cream/50">{esc(category["name"])}</span>' if category else ""
        finished = index in done
        label = "Reprendre" if finished else "Plat terminé"
        style = " text-cream/40 line-through" if finished else ""
        dishes.append(
            f"""
            <li class="border-t border-cream/10 py-2">
              <div class="flex items-start justify-between gap-2">
                <p class="min-w-0 text-base{style}"><span class="tabular-nums">{esc(line.get('quantity'))} ×</span> {esc(line.get('name'))}{station}{extra}{instruction}</p>
                <form method="post" action="/admin/cuisine/ligne">{hidden('csrf', ctx.session['csrf'])}{_keep(board['filters'])}{hidden('commande', order['id'])}{hidden('index', index)}{hidden('fait', '0' if finished else '1')}<button class="inline-flex min-h-11 items-center border border-cream/40 px-3 text-sm" type="submit">{label}</button></form>
              </div>
            </li>
            """
        )
    border = {"urgent": "border-terracotta", "attention": "border-saffron", "normal": "border-cream/20"}[state]
    issue = (order["kitchen_issue"] or "").strip()
    issue_html = ""
    if issue:
        issue_html = f"""
        <p class="mt-3 border border-saffron px-3 py-2 text-sm">Problème : {esc(issue)}</p>
        <form class="mt-2" method="post" action="/admin/cuisine/probleme">{hidden('csrf', ctx.session['csrf'])}{_keep(board['filters'])}{hidden('commande', order['id'])}{hidden('probleme', '')}<button class="text-sm underline" type="submit">Effacer le problème</button></form>
        """
    created = _moment(order["created_at"]).astimezone(PARIS)
    slot = ""
    if order["mode"] == "pickup" and order["start_time"]:
        slot = f' · retrait {esc(order["start_time"])}'
    remaining = _other_station_count(order, board, done)
    others = f'<p class="mt-2 text-sm text-cream/70">{remaining} plat{"s" if remaining != 1 else ""} hors de ce poste.</p>' if remaining else ""
    return f"""
    <article class="border {border} bg-night p-3" data-order="{order['id']}">
      <div class="flex items-start justify-between gap-2">
        <a class="font-display text-2xl leading-none" href="/admin/commandes/{order['id']}">{esc(order['public_ref'])}</a>
        <p class="text-right text-sm"><span class="font-medium">{LEVEL_LABEL[state]}</span><br><time data-since="{esc(order['created_at'])}">{esc(_elapsed(created, board['now']))}</time></p>
      </div>
      <p class="mt-2 text-sm">Reçue à {created.strftime('%H:%M')}{slot}</p>
      <p class="text-sm">{esc(MODE_LABEL.get(order['mode'], order['mode']))}</p>
      <p class="mt-1 text-sm">{esc(order['customer_name'])}</p>
      <p class="text-sm text-cream/70">{esc(order['phone'])}</p>
      <ul class="mt-2">{''.join(dishes) or '<li class="border-t border-cream/10 py-2 text-sm text-cream/50">Aucun plat de ce poste.</li>'}</ul>
      {others}
      {issue_html}
      <div class="mt-3 grid gap-2">{_actions(ctx, board, order, done)}</div>
    </article>
    """


def _actions(ctx, board, order, done):
    filters = board["filters"]
    keep = _keep(filters)
    token = hidden("csrf", ctx.session["csrf"])
    primary = ""
    status = order["status"]
    if status == "received":
        primary = _status_button(token, keep, order["id"], "accepted", "Accepter")
    elif status == "accepted":
        primary = _status_button(token, keep, order["id"], "preparing", "Démarrer")
    elif status == "preparing" and not filters["poste"]:
        primary = f"""
        <form method="post" action="/admin/cuisine/prete">{token}{keep}{hidden('commande', order['id'])}
          <label class="flex min-h-11 items-start gap-2 text-sm"><input type="checkbox" name="confirmer" value="1"><span>Tous les postes ont fini</span></label>
          <button class="mt-2 inline-flex min-h-12 w-full items-center justify-center bg-terracotta px-3 text-sm font-medium text-cream" type="submit">Commande prête</button>
        </form>
        """
    elif status == "ready" and order["mode"] == "delivery":
        primary = _status_button(token, keep, order["id"], "out_for_delivery", "Partie en livraison")
    elif status in {"ready", "out_for_delivery"}:
        primary = f"""
        <form method="post" action="/admin/commandes/{order['id']}/statut">{token}{keep}{hidden('retour', 'service')}{hidden('statut', 'completed')}
          <label class="flex min-h-11 items-start gap-2 text-sm"><input type="checkbox" name="confirmer" value="1"><span>Je confirme la clôture</span></label>
          <button class="mt-2 inline-flex min-h-12 w-full items-center justify-center bg-cream px-3 text-sm font-medium text-ink" type="submit">Terminée</button>
        </form>
        """
    problem = f"""
    <details>
      <summary class="flex min-h-11 cursor-pointer items-center text-sm">Signaler un problème</summary>
      <form class="mt-2 grid gap-2" method="post" action="/admin/cuisine/probleme">{token}{keep}{hidden('commande', order['id'])}
        <input class="min-h-12 border border-cream/30 bg-transparent px-3 text-cream" name="probleme" maxlength="280" value="{esc(order['kitchen_issue'] or '')}">
        <button class="inline-flex min-h-12 items-center justify-center border border-cream/40 text-sm" type="submit">Enregistrer</button>
      </form>
    </details>
    """
    cancel = f"""
    <details>
      <summary class="flex min-h-11 cursor-pointer items-center text-sm">Annuler</summary>
      <form class="mt-2" method="post" action="/admin/commandes/{order['id']}/statut">{token}{keep}{hidden('retour', 'service')}{hidden('statut', 'cancelled')}
        <label class="flex min-h-11 items-start gap-2 text-sm"><input type="checkbox" name="confirmer" value="1"><span>Je confirme l'annulation</span></label>
        <button class="mt-2 inline-flex min-h-12 w-full items-center justify-center border border-terracotta text-sm text-terracotta" type="submit">Annuler la commande</button>
      </form>
    </details>
    """
    detail = f'<a class="inline-flex min-h-11 items-center text-sm underline" href="/admin/commandes/{order["id"]}">Détail</a>'
    return primary + problem + cancel + detail


def _status_button(token, keep, order_id, status, label):
    return f"""
    <form method="post" action="/admin/commandes/{order_id}/statut">{token}{keep}{hidden('retour', 'service')}{hidden('statut', status)}
      <button class="inline-flex min-h-12 w-full items-center justify-center bg-terracotta px-3 text-sm font-medium text-cream" type="submit">{esc(label)}</button>
    </form>
    """


def _history_view(history, filters):
    if not history["rows"]:
        return '<p class="border border-cream/20 px-4 py-8 text-sm text-cream/70">Aucune commande terminée aujourd\'hui. Les journées précédentes sont dans Commandes.</p>'
    rows = []
    for order in history["rows"]:
        created = _moment(order["created_at"]).astimezone(PARIS)
        rows.append(
            f'<li class="flex flex-wrap items-baseline justify-between gap-2 border-b border-cream/15 py-3"><a class="font-display text-2xl" href="/admin/commandes/{order["id"]}">{esc(order["public_ref"])}</a><span class="text-sm">{esc(order["customer_name"])} · {esc(MODE_LABEL.get(order["mode"], order["mode"]))} · {created.strftime("%H:%M")}</span></li>'
        )
    links = ""
    if history["pages"] > 1:
        prev_page = max(1, history["page"] - 1)
        next_page = min(history["pages"], history["page"] + 1)
        links = f'<p class="mt-4 flex gap-3 text-sm"><a class="underline" href="{esc(_link(filters, page=str(prev_page)))}">Page précédente</a><span>{history["page"]} / {history["pages"]}</span><a class="underline" href="{esc(_link(filters, page=str(next_page)))}">Page suivante</a></p>'
    return f'<section class="border border-cream/15 bg-night-2 px-4"><h2 class="py-4 font-display text-2xl">Terminées aujourd\'hui</h2><ul>{"".join(rows)}</ul>{links}<p class="py-4 text-sm text-cream/60"><a class="underline" href="/admin/commandes?statut=completed">Toutes les commandes terminées</a></p></section>'


def _metrics(orders, done_map, now, limits, conn):
    urgent = sum(1 for order in orders if level_for(order, now, limits) == "urgent")
    average = average_prep_minutes(conn, now)
    return {
        "waiting": sum(1 for order in orders if order["status"] in {"received", "accepted"}),
        "preparing": sum(1 for order in orders if order["status"] == "preparing"),
        "urgent": urgent,
        "ready": sum(1 for order in orders if order["status"] == "ready"),
        "average": f"{average} min" if average is not None else "—",
    }


def _open_orders(conn):
    marks = ",".join("?" for _ in OPEN_STATUSES)
    return conn.execute(
        f"""
        SELECT o.*, s.slot_date, s.start_time, s.end_time
        FROM orders o
        LEFT JOIN pickup_slots s ON s.id = o.slot_id
        WHERE o.status IN ({marks})
          AND NOT (o.payment_method = 'stripe' AND IFNULL(o.payment_status, '') != 'paid')
        ORDER BY o.created_at, o.id
        """,
        OPEN_STATUSES,
    ).fetchall()


def _history(conn, page, now):
    start = datetime.combine(now.date(), time.min, tzinfo=PARIS).astimezone(timezone.utc)
    total = conn.execute(
        "SELECT COUNT(*) AS n FROM orders WHERE status = 'completed' AND created_at >= ?",
        (iso(start),),
    ).fetchone()["n"]
    pages = max(1, (total + HISTORY_PAGE - 1) // HISTORY_PAGE)
    page = min(page, pages)
    rows = conn.execute(
        """
        SELECT * FROM orders
        WHERE status = 'completed' AND created_at >= ?
        ORDER BY id DESC
        LIMIT ? OFFSET ?
        """,
        (iso(start), HISTORY_PAGE, (page - 1) * HISTORY_PAGE),
    ).fetchall()
    return {"rows": rows, "page": page, "pages": pages}


def _category_map(conn):
    rows = conn.execute(
        """
        SELECT p.id, c.slug, c.name
        FROM products p
        JOIN categories c ON c.id = p.category_id
        """
    ).fetchall()
    return {row["id"]: {"slug": row["slug"], "name": row["name"]} for row in rows}


def _done_map(conn, order_ids):
    if not order_ids:
        return {}
    marks = ",".join("?" for _ in order_ids)
    rows = conn.execute(
        f"SELECT order_id, line_index FROM kitchen_lines WHERE done = 1 AND order_id IN ({marks})",
        order_ids,
    ).fetchall()
    found = {}
    for row in rows:
        found.setdefault(row["order_id"], set()).add(row["line_index"])
    return found


def _done_indexes(conn, order_id):
    rows = conn.execute(
        "SELECT line_index FROM kitchen_lines WHERE order_id = ? AND done = 1",
        (order_id,),
    ).fetchall()
    return {row["line_index"] for row in rows}


def _filters(conn, query):
    def first(key):
        value = query.get(key) if isinstance(query, dict) else None
        if isinstance(value, list):
            value = value[0] if value else ""
        return (value or "").strip()

    poste = first("poste")
    known = {row["slug"] for row in conn.execute("SELECT slug FROM categories")}
    if poste not in known:
        poste = ""
    mode = first("mode")
    if mode not in {"pickup", "delivery"}:
        mode = ""
    heure = first("heure")
    if not (heure.isdigit() and 0 <= int(heure) <= 23):
        heure = ""
    vue = "terminees" if first("vue") == "terminees" else ""
    page_raw = first("page")
    page = int(page_raw) if page_raw.isdigit() and int(page_raw) > 0 else 1
    return {"q": first("q")[:40], "poste": poste, "mode": mode, "heure": heure, "vue": vue, "page": page}


def _matches(order, filters):
    if filters["mode"] and order["mode"] != filters["mode"]:
        return False
    if filters["q"]:
        haystack = " ".join((order["public_ref"], order["customer_name"], order["phone"])).lower()
        if filters["q"].lower() not in haystack:
            return False
    if filters["heure"]:
        if not _order_hour(order) == int(filters["heure"]):
            return False
    if filters["poste"]:
        return any(category and category["slug"] == filters["poste"] for _index, _line, category in _annotated(order))
    return True


def _order_hour(order):
    if order["mode"] == "pickup" and order["start_time"]:
        return int(order["start_time"].split(":", 1)[0])
    return _moment(order["created_at"]).astimezone(PARIS).hour


def _hours(orders):
    return sorted({_order_hour(order) for order in orders})


def _annotated(order, cache=None):
    return _annotate(order)


def _visible_lines(order, board):
    rows = _annotate(order, board.get("category_map"))
    if not board["filters"]["poste"]:
        return rows
    return [row for row in rows if row[2] and row[2]["slug"] == board["filters"]["poste"]]


def _other_station_count(order, board, done):
    if not board["filters"]["poste"]:
        return 0
    count = 0
    for index, _line, category in _annotate(order, board.get("category_map")):
        if index in done:
            continue
        if not category or category["slug"] != board["filters"]["poste"]:
            count += 1
    return count


def _annotate(order, category_map=None):
    if category_map is None:
        category_map = order.get("_categories") or {}
    rows = []
    for index, line in enumerate(_lines(order)):
        product_id = line.get("product_id")
        category = category_map.get(int(product_id)) if product_id else None
        rows.append((index, line, category))
    return rows


def _lines(order):
    try:
        lines = json.loads(order["snapshot_json"])
    except (TypeError, json.JSONDecodeError):
        return []
    return lines if isinstance(lines, list) else []


def _keep(filters):
    return "".join(hidden(key, filters[key]) for key in ("poste", "q", "mode", "heure", "vue", "page") if filters[key])


def _link(filters, **changes):
    data = dict(filters)
    data.update(changes)
    kept = [(key, str(data[key])) for key in ("poste", "q", "mode", "heure", "vue", "page") if data.get(key)]
    return "/admin/cuisine" + (("?" + urlencode(kept)) if kept else "")


def _poll_url(filters):
    return "/admin/cuisine/fragment" + _link(filters)[len("/admin/cuisine") :]


def _station_link(filters, row):
    return f'<a class="{_chip(filters["poste"] == row["slug"])}" href="{esc(_link(filters, poste=row["slug"]))}">{esc(row["name"])}</a>'


def _chip(active):
    tone = "border-cream bg-cream text-ink" if active else "border-cream/30 text-cream"
    return f"inline-flex min-h-11 shrink-0 items-center border px-3 text-sm {tone}"


def _elapsed(created, now):
    minutes = max(0, int((now - created).total_seconds() // 60))
    if minutes < 60:
        return f"{minutes} min"
    return f"{minutes // 60} h {minutes % 60:02d}"


def _field(order, key):
    try:
        return order[key]
    except (KeyError, IndexError):
        return None


def _moment(value):
    moment = datetime.fromisoformat(value)
    if moment.tzinfo is None:
        moment = moment.replace(tzinfo=timezone.utc)
    return moment


def _minutes(value, default):
    try:
        number = int(str(value).strip())
    except (TypeError, ValueError):
        return default
    if 1 <= number <= 180:
        return number
    return default


def attach_categories(conn, orders):
    mapping = _category_map(conn)
    attached = []
    for order in orders:
        row = dict(order)
        row["_categories"] = mapping
        attached.append(row)
    return attached, mapping
