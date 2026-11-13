from app.auth import utc_now, iso
from app.pricing import quote_product


def line_key(product_id, choice_ids, notes):
    choices = ",".join(str(int(item)) for item in sorted(choice_ids))
    note = " ".join((notes or "").split())
    return f"{int(product_id)}|{choices}|{note}"


def get_or_create_cart(conn, session_id):
    row = conn.execute("SELECT * FROM carts WHERE session_id = ?", (session_id,)).fetchone()
    if row:
        return row
    cur = conn.execute(
        "INSERT INTO carts (session_id, updated_at) VALUES (?, ?)",
        (session_id, iso(utc_now())),
    )
    return conn.execute("SELECT * FROM carts WHERE id = ?", (cur.lastrowid,)).fetchone()


def cart_count(conn, session_id):
    row = conn.execute(
        """
        SELECT COALESCE(SUM(ci.quantity), 0) AS n
        FROM cart_items ci
        JOIN carts c ON c.id = ci.cart_id
        WHERE c.session_id = ?
        """,
        (session_id,),
    ).fetchone()
    return int(row["n"] if row else 0)


def _choice_ids(conn, item_id):
    rows = conn.execute(
        "SELECT choice_id FROM cart_item_choices WHERE item_id = ? ORDER BY choice_id",
        (item_id,),
    ).fetchall()
    return [row["choice_id"] for row in rows]


def cart_lines(conn, session_id, clock=None):
    cart = conn.execute("SELECT * FROM carts WHERE session_id = ?", (session_id,)).fetchone()
    if not cart:
        return None, []
    items = conn.execute(
        "SELECT * FROM cart_items WHERE cart_id = ? ORDER BY id",
        (cart["id"],),
    ).fetchall()
    lines = []
    for item in items:
        quote = quote_product(
            conn,
            item["product_id"],
            _choice_ids(conn, item["id"]),
            item["quantity"],
            item["notes"],
            clock=clock,
        )
        lines.append((item, quote))
    return cart, lines


def add_item(conn, session_id, product_id, choice_ids, quantity, notes="", clock=None):
    quote = quote_product(conn, product_id, choice_ids, quantity, notes, clock=clock)
    if not quote.product or quote.issues:
        return quote
    cart = get_or_create_cart(conn, session_id)
    key = line_key(product_id, [choice["id"] for choice in quote.choice_rows], quote.notes)
    existing = conn.execute(
        "SELECT * FROM cart_items WHERE cart_id = ? AND line_key = ?",
        (cart["id"], key),
    ).fetchone()
    if existing:
        new_qty = existing["quantity"] + quote.quantity
        if new_qty > 20:
            quote.issues.append("La quantite maximale pour cette personnalisation est 20.")
            return quote
        conn.execute("UPDATE cart_items SET quantity = ? WHERE id = ?", (new_qty, existing["id"]))
    else:
        cur = conn.execute(
            """
            INSERT INTO cart_items (cart_id, product_id, quantity, notes, line_key)
            VALUES (?, ?, ?, ?, ?)
            """,
            (cart["id"], product_id, quote.quantity, quote.notes, key),
        )
        for choice in quote.choice_rows:
            conn.execute(
                "INSERT INTO cart_item_choices (item_id, choice_id) VALUES (?, ?)",
                (cur.lastrowid, choice["id"]),
            )
    conn.execute("UPDATE carts SET updated_at = ? WHERE id = ?", (iso(utc_now()), cart["id"]))
    return quote


def update_quantity(conn, session_id, item_id, quantity):
    cart = conn.execute("SELECT * FROM carts WHERE session_id = ?", (session_id,)).fetchone()
    if not cart:
        return "Panier introuvable."
    item = conn.execute(
        "SELECT * FROM cart_items WHERE id = ? AND cart_id = ?",
        (item_id, cart["id"]),
    ).fetchone()
    if not item:
        return "Article introuvable."
    quantity = int(quantity)
    if quantity < 1 or quantity > 20:
        return "La quantite doit etre comprise entre 1 et 20."
    conn.execute("UPDATE cart_items SET quantity = ? WHERE id = ?", (quantity, item_id))
    conn.execute("UPDATE carts SET updated_at = ? WHERE id = ?", (iso(utc_now()), cart["id"]))
    return None


def remove_item(conn, session_id, item_id):
    cart = conn.execute("SELECT * FROM carts WHERE session_id = ?", (session_id,)).fetchone()
    if not cart:
        return
    conn.execute(
        "DELETE FROM cart_items WHERE id = ? AND cart_id = ?",
        (item_id, cart["id"]),
    )


def set_promo(conn, session_id, code):
    cart = get_or_create_cart(conn, session_id)
    cleaned = (code or "").strip()
    conn.execute(
        "UPDATE carts SET promo_code = ?, updated_at = ? WHERE id = ?",
        (cleaned or None, iso(utc_now()), cart["id"]),
    )


def clear_cart(conn, cart_id):
    conn.execute("DELETE FROM cart_items WHERE cart_id = ?", (cart_id,))
    conn.execute(
        "UPDATE carts SET promo_code = NULL, updated_at = ? WHERE id = ?",
        (iso(utc_now()), cart_id),
    )
