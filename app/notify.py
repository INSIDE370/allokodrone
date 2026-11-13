"""File d'attente des notifications. Rien n'est marqué envoyé sans fournisseur."""

import json
import os
import urllib.request

from app.auth import iso, utc_now


def unseen_count(conn):
    row = conn.execute("SELECT COUNT(*) AS n FROM notifications WHERE seen = 0").fetchone()
    return int(row["n"])


def mark_seen(conn):
    conn.execute("UPDATE notifications SET seen = 1 WHERE seen = 0")


def record(conn, order_id, event):
    url = os.environ.get("NOTIFY_WEBHOOK_URL", "").strip()
    status = "skipped"
    detail = "Aucun fournisseur d'e-mail ou de SMS n'est configuré."
    if url.startswith("https://"):
        status, detail = _post(url, {"orderId": order_id, "event": event})
    conn.execute(
        """
        INSERT INTO notifications (order_id, event, channel, status, detail, created_at)
        VALUES (?, ?, 'webhook', ?, ?, ?)
        """,
        (order_id, event, status, detail, iso(utc_now())),
    )
    return status


def _post(url, payload):
    request = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        method="POST",
        headers={"Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(request, timeout=10) as response:
            if 200 <= response.status < 300:
                return "sent", "Notification remise au fournisseur."
            return "failed", f"Le fournisseur a répondu {response.status}."
    except Exception:
        return "failed", "Le fournisseur de notification est injoignable."
