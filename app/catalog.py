def categories(conn):
    return conn.execute("SELECT * FROM categories ORDER BY sort_order, id").fetchall()


def list_products(conn, category_slug=None, query=None):
    sql = """
        SELECT p.*, c.slug AS category_slug, c.name AS category_name
        FROM products p
        JOIN categories c ON c.id = p.category_id
        WHERE 1 = 1
    """
    args = []
    if category_slug:
        sql += " AND c.slug = ?"
        args.append(category_slug)
    if query:
        sql += " AND (p.name LIKE ? OR p.description LIKE ?)"
        like = f"%{query.strip()}%"
        args.extend([like, like])
    sql += " ORDER BY c.sort_order, p.sort_order, p.id"
    return conn.execute(sql, args).fetchall()


def featured_products(conn):
    return conn.execute(
        """
        SELECT p.*, c.name AS category_name, c.slug AS category_slug
        FROM products p
        JOIN categories c ON c.id = p.category_id
        WHERE p.featured = 1
        ORDER BY p.sort_order, p.id
        """
    ).fetchall()


def product_by_slug(conn, slug):
    return conn.execute(
        """
        SELECT p.*, c.name AS category_name, c.slug AS category_slug
        FROM products p
        JOIN categories c ON c.id = p.category_id
        WHERE p.slug = ?
        """,
        (slug,),
    ).fetchone()


def product_by_id(conn, product_id):
    return conn.execute(
        """
        SELECT p.*, c.name AS category_name, c.slug AS category_slug
        FROM products p
        JOIN categories c ON c.id = p.category_id
        WHERE p.id = ?
        """,
        (product_id,),
    ).fetchone()


def groups_for_product(conn, product_id):
    groups = conn.execute(
        """
        SELECT * FROM option_groups
        WHERE product_id = ?
        ORDER BY sort_order, id
        """,
        (product_id,),
    ).fetchall()
    result = []
    for group in groups:
        choices = conn.execute(
            """
            SELECT * FROM option_choices
            WHERE group_id = ?
            ORDER BY sort_order, id
            """,
            (group["id"],),
        ).fetchall()
        result.append((group, choices))
    return result


def choice_by_id(conn, choice_id):
    return conn.execute(
        """
        SELECT ch.*, g.product_id, g.name AS group_name, g.required, g.min_select, g.max_select, g.id AS group_id
        FROM option_choices ch
        JOIN option_groups g ON g.id = ch.group_id
        WHERE ch.id = ?
        """,
        (choice_id,),
    ).fetchone()
