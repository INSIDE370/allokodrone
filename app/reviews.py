"""Avis clients liés aux commandes terminées, avec modération restaurant."""

from __future__ import annotations

import base64
import binascii
import re
from datetime import datetime, timedelta, timezone
from pathlib import Path

from app.auth import iso, utc_now
from app.db import ROOT
from app.schedule import PARIS

UPLOAD_DIR = ROOT / "data" / "uploads" / "reviews"
STATUSES = ("published", "hidden", "pending")
EDIT_WINDOW = timedelta(hours=48)
PAGE_SIZE = 12


def ensure_review_tables(conn):
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS reviews (
          id INTEGER PRIMARY KEY,
          order_id INTEGER UNIQUE REFERENCES orders(id),
          session_id TEXT,
          user_id INTEGER REFERENCES users(id),
          author TEXT NOT NULL,
          stars INTEGER NOT NULL,
          body TEXT NOT NULL,
          food_stars INTEGER,
          delivery_stars INTEGER,
          service_stars INTEGER,
          photo_path TEXT,
          verified INTEGER NOT NULL DEFAULT 0,
          status TEXT NOT NULL DEFAULT 'published',
          useful_count INTEGER NOT NULL DEFAULT 0,
          reply_body TEXT,
          reply_at TEXT,
          reply_by INTEGER REFERENCES users(id),
          hidden_reason TEXT,
          hidden_at TEXT,
          hidden_by INTEGER REFERENCES users(id),
          created_at TEXT NOT NULL,
          updated_at TEXT
        );

        CREATE TABLE IF NOT EXISTS review_votes (
          review_id INTEGER NOT NULL REFERENCES reviews(id),
          session_id TEXT NOT NULL,
          created_at TEXT NOT NULL,
          PRIMARY KEY (review_id, session_id)
        );

        CREATE TABLE IF NOT EXISTS review_reports (
          id INTEGER PRIMARY KEY,
          review_id INTEGER NOT NULL REFERENCES reviews(id),
          session_id TEXT,
          reason TEXT NOT NULL,
          created_at TEXT NOT NULL
        );

        CREATE INDEX IF NOT EXISTS idx_reviews_status_created ON reviews(status, created_at DESC);
        CREATE INDEX IF NOT EXISTS idx_reviews_stars ON reviews(stars);
        """
    )
    _migrate_guest_reviews(conn)


def _migrate_guest_reviews(conn):
    exists = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='guest_reviews'"
    ).fetchone()
    if not exists:
        return
    rows = conn.execute(
        "SELECT id, session_id, author, stars, body, created_at FROM guest_reviews ORDER BY id"
    ).fetchall()
    for row in rows:
        already = conn.execute(
            """
            SELECT id FROM reviews
            WHERE order_id IS NULL AND author = ? AND body = ? AND created_at = ?
            """,
            (row["author"], row["body"], row["created_at"]),
        ).fetchone()
        if already:
            continue
        conn.execute(
            """
            INSERT INTO reviews (
              order_id, session_id, user_id, author, stars, body, verified, status,
              useful_count, created_at
            ) VALUES (NULL, ?, NULL, ?, ?, ?, 0, 'published', 0, ?)
            """,
            (row["session_id"], row["author"], row["stars"], row["body"], row["created_at"]),
        )


def _plain(value, limit):
    if not isinstance(value, str):
        return ""
    return " ".join(value.replace("\x00", " ").split())[:limit]


def _star(value, required=False):
    try:
        stars = int(value)
    except (TypeError, ValueError):
        return None if not required else 0
    if stars < 1 or stars > 5:
        return None if not required else 0
    return stars


def _date_label(raw):
    moment = datetime.fromisoformat(raw)
    if moment.tzinfo is None:
        moment = moment.replace(tzinfo=timezone.utc)
    return moment.astimezone(PARIS).strftime("%d/%m/%Y")


def _initials(author):
    parts = [part for part in re.split(r"\s+", author.strip()) if part]
    if not parts:
        return "?"
    if len(parts) == 1:
        return parts[0][:2].upper()
    return (parts[0][0] + parts[-1][0]).upper()


def _public_item(row, *, voted=False, can_edit=False):
    item = {
        "id": row["id"],
        "author": row["author"],
        "initials": _initials(row["author"]),
        "stars": row["stars"],
        "body": row["body"],
        "dateLabel": _date_label(row["created_at"]),
        "verified": bool(row["verified"]),
        "usefulCount": row["useful_count"] or 0,
        "votedUseful": voted,
        "canEdit": can_edit,
        "photoUrl": f"/uploads/reviews/{Path(row['photo_path']).name}" if row["photo_path"] else None,
        "foodStars": row["food_stars"],
        "deliveryStars": row["delivery_stars"],
        "serviceStars": row["service_stars"],
        "reply": None,
    }
    if row["reply_body"]:
        item["reply"] = {
            "body": row["reply_body"],
            "dateLabel": _date_label(row["reply_at"]) if row["reply_at"] else "",
        }
    return item


def _histogram(conn):
    counts = {n: 0 for n in range(1, 6)}
    for row in conn.execute(
        "SELECT stars, COUNT(*) AS n FROM reviews WHERE status = 'published' GROUP BY stars"
    ):
        counts[int(row["stars"])] = row["n"]
    return [{"stars": n, "count": counts[n]} for n in range(5, 0, -1)]


def board(conn, *, note=None, sort="date", page=1, session_id="", user_id=None):
    where = ["status = 'published'"]
    args = []
    if note in {1, 2, 3, 4, 5}:
        where.append("stars = ?")
        args.append(note)
    clause = " AND ".join(where)
    total = conn.execute(f"SELECT COUNT(*) AS n FROM reviews WHERE {clause}", args).fetchone()["n"]
    avg_row = conn.execute(
        "SELECT AVG(stars) AS avg FROM reviews WHERE status = 'published'"
    ).fetchone()
    average = round(float(avg_row["avg"]), 1) if avg_row["avg"] is not None else None
    order_sql = {
        "pertinence": "useful_count DESC, stars DESC, datetime(created_at) DESC, id DESC",
        "note": "stars DESC, datetime(created_at) DESC, id DESC",
        "date": "datetime(created_at) DESC, id DESC",
    }.get(sort, "datetime(created_at) DESC, id DESC")
    page = max(1, int(page or 1))
    offset = (page - 1) * PAGE_SIZE
    rows = conn.execute(
        f"""
        SELECT * FROM reviews
        WHERE {clause}
        ORDER BY {order_sql}
        LIMIT ? OFFSET ?
        """,
        (*args, PAGE_SIZE, offset),
    ).fetchall()
    voted = set()
    if session_id and rows:
        ids = ",".join("?" for _ in rows)
        voted = {
            item["review_id"]
            for item in conn.execute(
                f"SELECT review_id FROM review_votes WHERE session_id = ? AND review_id IN ({ids})",
                (session_id, *[row["id"] for row in rows]),
            )
        }
    items = []
    for row in rows:
        own = (session_id and row["session_id"] == session_id) or (
            user_id and row["user_id"] and row["user_id"] == user_id
        )
        editable = bool(own and _within_edit_window(row))
        items.append(_public_item(row, voted=row["id"] in voted, can_edit=editable))
    pages = max(1, (total + PAGE_SIZE - 1) // PAGE_SIZE)
    return {
        "reviews": items,
        "average": average,
        "count": conn.execute(
            "SELECT COUNT(*) AS n FROM reviews WHERE status = 'published'"
        ).fetchone()["n"],
        "filteredCount": total,
        "histogram": _histogram(conn),
        "page": page,
        "pageSize": PAGE_SIZE,
        "pages": pages,
        "sort": sort if sort in {"date", "pertinence", "note"} else "date",
        "note": note if note in {1, 2, 3, 4, 5} else None,
    }


def _within_edit_window(row):
    if row["status"] != "published":
        return False
    created = datetime.fromisoformat(row["created_at"])
    if created.tzinfo is None:
        created = created.replace(tzinfo=timezone.utc)
    return utc_now() - created <= EDIT_WINDOW


def reviewable_order(conn, public_ref, session_id, user_id=None):
    if not isinstance(public_ref, str) or not public_ref.startswith("AK-") or len(public_ref) > 20:
        return None, "Commande introuvable."
    order = conn.execute("SELECT * FROM orders WHERE public_ref = ?", (public_ref,)).fetchone()
    if not order:
        return None, "Commande introuvable."
    owned = order["session_id"] == session_id or (
        user_id and order["user_id"] and order["user_id"] == user_id
    )
    if not owned:
        return None, "Commande introuvable."
    if order["status"] != "completed":
        return None, "L'avis s'ouvre quand la commande est terminée."
    existing = conn.execute("SELECT id FROM reviews WHERE order_id = ?", (order["id"],)).fetchone()
    if existing:
        return None, "Un avis existe déjà pour cette commande."
    return order, None


def create_from_order(conn, payload, session_id, user_id=None):
    order, error = reviewable_order(conn, payload.get("orderRef") or payload.get("ref"), session_id, user_id)
    if error:
        return None, [error]
    author = _plain(payload.get("nom") or order["customer_name"], 40)
    raw = payload.get("message")
    body = _plain(raw, 800)
    stars = _star(payload.get("note"), required=True)
    food = _star(payload.get("notePlats"))
    delivery = _star(payload.get("noteLivraison"))
    service = _star(payload.get("noteService"))
    errors = []
    if len(author) < 2:
        errors.append("Indiquez votre prénom.")
    if not stars:
        errors.append("Choisissez une note de 1 à 5.")
    if isinstance(raw, str) and len(raw.strip()) > 800:
        errors.append("L'avis dépasse 800 caractères.")
    elif len(body) < 8:
        errors.append("Écrivez un avis d'au moins quelques mots.")
    photo_path, photo_error = _save_photo(payload.get("photo"), None)
    if photo_error:
        errors.append(photo_error)
    if errors:
        return None, errors
    now = iso(utc_now())
    cur = conn.execute(
        """
        INSERT INTO reviews (
          order_id, session_id, user_id, author, stars, body,
          food_stars, delivery_stars, service_stars, photo_path,
          verified, status, useful_count, created_at, updated_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 1, 'published', 0, ?, ?)
        """,
        (
            order["id"],
            session_id,
            user_id,
            author,
            stars,
            body,
            food,
            delivery if order["mode"] == "delivery" else None,
            service,
            photo_path,
            now,
            now,
        ),
    )
    review_id = cur.lastrowid
    if photo_path:
        final = _finalize_photo(photo_path, review_id)
        conn.execute("UPDATE reviews SET photo_path = ? WHERE id = ?", (final, review_id))
    row = conn.execute("SELECT * FROM reviews WHERE id = ?", (review_id,)).fetchone()
    return _public_item(row, can_edit=True), None


def update_review(conn, review_id, payload, session_id, user_id=None):
    row = conn.execute("SELECT * FROM reviews WHERE id = ?", (review_id,)).fetchone()
    if not row:
        return None, ["Avis introuvable."]
    own = (session_id and row["session_id"] == session_id) or (
        user_id and row["user_id"] and row["user_id"] == user_id
    )
    if not own or not _within_edit_window(row):
        return None, ["Cet avis ne peut plus être modifié."]
    author = _plain(payload.get("nom") or row["author"], 40)
    raw = payload.get("message")
    body = _plain(raw if raw is not None else row["body"], 800)
    stars = _star(payload.get("note"), required=True) or row["stars"]
    errors = []
    if len(author) < 2:
        errors.append("Indiquez votre prénom.")
    if not stars:
        errors.append("Choisissez une note de 1 à 5.")
    if len(body) < 8:
        errors.append("Écrivez un avis d'au moins quelques mots.")
    if errors:
        return None, errors
    conn.execute(
        """
        UPDATE reviews
        SET author = ?, stars = ?, body = ?,
            food_stars = ?, delivery_stars = ?, service_stars = ?,
            updated_at = ?
        WHERE id = ?
        """,
        (
            author,
            stars,
            body,
            _star(payload.get("notePlats")) if "notePlats" in payload else row["food_stars"],
            _star(payload.get("noteLivraison")) if "noteLivraison" in payload else row["delivery_stars"],
            _star(payload.get("noteService")) if "noteService" in payload else row["service_stars"],
            iso(utc_now()),
            review_id,
        ),
    )
    updated = conn.execute("SELECT * FROM reviews WHERE id = ?", (review_id,)).fetchone()
    return _public_item(updated, can_edit=True), None


def delete_review(conn, review_id, session_id, user_id=None, *, admin=False):
    row = conn.execute("SELECT * FROM reviews WHERE id = ?", (review_id,)).fetchone()
    if not row:
        return ["Avis introuvable."]
    own = (session_id and row["session_id"] == session_id) or (
        user_id and row["user_id"] and row["user_id"] == user_id
    )
    if not admin and (not own or not _within_edit_window(row)):
        return ["Cet avis ne peut plus être supprimé."]
    if row["photo_path"]:
        path = ROOT / row["photo_path"]
        if path.is_file():
            path.unlink()
    conn.execute("DELETE FROM review_votes WHERE review_id = ?", (review_id,))
    conn.execute("DELETE FROM review_reports WHERE review_id = ?", (review_id,))
    conn.execute("DELETE FROM reviews WHERE id = ?", (review_id,))
    return []


def mark_useful(conn, review_id, session_id):
    row = conn.execute(
        "SELECT id FROM reviews WHERE id = ? AND status = 'published'", (review_id,)
    ).fetchone()
    if not row:
        return None, "Avis introuvable."
    existing = conn.execute(
        "SELECT 1 FROM review_votes WHERE review_id = ? AND session_id = ?",
        (review_id, session_id),
    ).fetchone()
    if existing:
        conn.execute(
            "DELETE FROM review_votes WHERE review_id = ? AND session_id = ?",
            (review_id, session_id),
        )
        conn.execute(
            """
            UPDATE reviews
            SET useful_count = CASE WHEN useful_count > 0 THEN useful_count - 1 ELSE 0 END
            WHERE id = ?
            """,
            (review_id,),
        )
        voted = False
    else:
        conn.execute(
            "INSERT INTO review_votes (review_id, session_id, created_at) VALUES (?, ?, ?)",
            (review_id, session_id, iso(utc_now())),
        )
        conn.execute(
            "UPDATE reviews SET useful_count = useful_count + 1 WHERE id = ?",
            (review_id,),
        )
        voted = True
    count = conn.execute(
        "SELECT useful_count FROM reviews WHERE id = ?", (review_id,)
    ).fetchone()["useful_count"]
    return {"usefulCount": count, "votedUseful": voted}, None


def report_review(conn, review_id, session_id, reason):
    row = conn.execute(
        "SELECT id FROM reviews WHERE id = ? AND status = 'published'", (review_id,)
    ).fetchone()
    if not row:
        return ["Avis introuvable."]
    text = _plain(reason, 240)
    if len(text) < 4:
        return ["Indiquez le motif du signalement."]
    recent = conn.execute(
        """
        SELECT COUNT(*) AS n FROM review_reports
        WHERE session_id = ? AND created_at >= ?
        """,
        (session_id, (utc_now() - timedelta(hours=1)).isoformat()),
    ).fetchone()["n"]
    if recent >= 8:
        return ["Trop de signalements. Réessayez plus tard."]
    conn.execute(
        """
        INSERT INTO review_reports (review_id, session_id, reason, created_at)
        VALUES (?, ?, ?, ?)
        """,
        (review_id, session_id, text, iso(utc_now())),
    )
    return []


def admin_stats(conn):
    published = conn.execute(
        "SELECT COUNT(*) AS n, AVG(stars) AS avg FROM reviews WHERE status = 'published'"
    ).fetchone()
    hidden = conn.execute(
        "SELECT COUNT(*) AS n FROM reviews WHERE status = 'hidden'"
    ).fetchone()["n"]
    reports = conn.execute("SELECT COUNT(*) AS n FROM review_reports").fetchone()["n"]
    verified = conn.execute(
        "SELECT COUNT(*) AS n FROM reviews WHERE status = 'published' AND verified = 1"
    ).fetchone()["n"]
    trend = []
    for row in conn.execute(
        """
        SELECT substr(created_at, 1, 10) AS day, COUNT(*) AS n, AVG(stars) AS avg
        FROM reviews
        WHERE status = 'published' AND created_at >= ?
        GROUP BY day
        ORDER BY day DESC
        LIMIT 14
        """,
        ((utc_now() - timedelta(days=14)).isoformat(),),
    ):
        trend.append(
            {
                "day": row["day"],
                "count": row["n"],
                "average": round(float(row["avg"]), 1) if row["avg"] is not None else None,
            }
        )
    trend.reverse()
    return {
        "count": published["n"] or 0,
        "average": round(float(published["avg"]), 1) if published["avg"] is not None else None,
        "hidden": hidden,
        "reports": reports,
        "verified": verified,
        "histogram": _histogram(conn),
        "trend": trend,
    }


def admin_list(conn, *, status="published", note=None, q=""):
    where = ["1 = 1"]
    args = []
    if status in STATUSES:
        where.append("r.status = ?")
        args.append(status)
    if note in {1, 2, 3, 4, 5}:
        where.append("r.stars = ?")
        args.append(note)
    text = _plain(q, 80)
    if text:
        where.append("(r.author LIKE ? OR r.body LIKE ? OR IFNULL(r.reply_body, '') LIKE ?)")
        needle = f"%{text}%"
        args.extend([needle, needle, needle])
    clause = " AND ".join(where)
    return conn.execute(
        f"""
        SELECT r.*, o.public_ref
        FROM reviews r
        LEFT JOIN orders o ON o.id = r.order_id
        WHERE {clause}
        ORDER BY datetime(r.created_at) DESC, r.id DESC
        LIMIT 100
        """,
        args,
    ).fetchall()


def hide_review(conn, review_id, admin_id, reason):
    text = _plain(reason, 240)
    if len(text) < 4:
        return ["Indiquez le motif du masquage."]
    row = conn.execute("SELECT id FROM reviews WHERE id = ?", (review_id,)).fetchone()
    if not row:
        return ["Avis introuvable."]
    conn.execute(
        """
        UPDATE reviews
        SET status = 'hidden', hidden_reason = ?, hidden_at = ?, hidden_by = ?, updated_at = ?
        WHERE id = ?
        """,
        (text, iso(utc_now()), admin_id, iso(utc_now()), review_id),
    )
    return []


def publish_review(conn, review_id):
    row = conn.execute("SELECT id FROM reviews WHERE id = ?", (review_id,)).fetchone()
    if not row:
        return ["Avis introuvable."]
    conn.execute(
        """
        UPDATE reviews
        SET status = 'published', hidden_reason = NULL, hidden_at = NULL, hidden_by = NULL, updated_at = ?
        WHERE id = ?
        """,
        (iso(utc_now()), review_id),
    )
    return []


def reply_review(conn, review_id, admin_id, body):
    text = _plain(body, 800)
    if len(text) < 4:
        return ["Écrivez la réponse du restaurant."]
    row = conn.execute("SELECT id FROM reviews WHERE id = ?", (review_id,)).fetchone()
    if not row:
        return ["Avis introuvable."]
    conn.execute(
        """
        UPDATE reviews
        SET reply_body = ?, reply_at = ?, reply_by = ?, updated_at = ?
        WHERE id = ?
        """,
        (text, iso(utc_now()), admin_id, iso(utc_now()), review_id),
    )
    return []


def order_review_state(conn, order, session_id, user_id=None):
    if not order or order["status"] != "completed":
        return {"canReview": False, "reviewId": None}
    row = conn.execute(
        "SELECT id, session_id, user_id FROM reviews WHERE order_id = ?",
        (order["id"],),
    ).fetchone()
    if row:
        own = (session_id and row["session_id"] == session_id) or (
            user_id and row["user_id"] and row["user_id"] == user_id
        )
        return {"canReview": False, "reviewId": row["id"] if own else None}
    owned = order["session_id"] == session_id or (
        user_id and order["user_id"] and order["user_id"] == user_id
    )
    return {"canReview": bool(owned), "reviewId": None}


def _save_photo(raw, review_id):
    if raw in (None, ""):
        return None, None
    if not isinstance(raw, str) or not raw.startswith("data:image/"):
        return None, "La photo doit être une image JPEG, PNG ou WebP."
    match = re.match(r"^data:image/(jpeg|jpg|png|webp);base64,(.+)$", raw, re.I | re.S)
    if not match:
        return None, "Format de photo non accepté."
    kind = match.group(1).lower().replace("jpg", "jpeg")
    try:
        data = base64.b64decode(match.group(2), validate=True)
    except (binascii.Error, ValueError):
        return None, "La photo est illisible."
    if len(data) > 2_000_000:
        return None, "La photo dépasse 2 Mo."
    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    suffix = {"jpeg": ".jpg", "png": ".png", "webp": ".webp"}[kind]
    name = f"tmp-{utc_now().timestamp():.0f}{suffix}" if review_id is None else f"{review_id}{suffix}"
    path = UPLOAD_DIR / name
    path.write_bytes(data)
    return str(path.relative_to(ROOT)).replace("\\", "/"), None


def _finalize_photo(tmp_relative, review_id):
    src = ROOT / tmp_relative
    if not src.is_file():
        return None
    suffix = src.suffix.lower() or ".jpg"
    dest = UPLOAD_DIR / f"{review_id}{suffix}"
    if dest.exists():
        dest.unlink()
    src.replace(dest)
    return str(dest.relative_to(ROOT)).replace("\\", "/")


def upload_file(path):
    if not path.startswith("/uploads/reviews/"):
        return None
    name = path.rsplit("/", 1)[-1]
    if not name or "/" in name or "\\" in name or ".." in name:
        return None
    target = (UPLOAD_DIR / name).resolve()
    if UPLOAD_DIR.resolve() not in target.parents and target.parent != UPLOAD_DIR.resolve():
        return None
    if not target.is_file():
        return None
    return target
