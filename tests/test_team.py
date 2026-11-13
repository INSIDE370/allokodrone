import os
import tempfile
import unittest
from urllib.parse import urlencode

from app.auth import create_staff, ensure_admin
from app.db import init_db
from app.seed import seed
from app.server import handle_http


class TeamSettingsTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.conn = init_db(os.path.join(self.tmp.name, "shop.db"))
        seed(self.conn)
        ensure_admin(self.conn, "admin@example.com", "admin-secret-1")
        self.conn.commit()

    def tearDown(self):
        self.conn.close()
        self.tmp.cleanup()

    def _admin_sid(self):
        opened = handle_http(self.conn, "GET", "/admin/connexion", {}, b"")
        sid = dict(opened.headers)["Set-Cookie"].split("sid=", 1)[1].split(";", 1)[0]
        csrf = self.conn.execute("SELECT csrf FROM sessions WHERE id = ?", (sid,)).fetchone()["csrf"]
        body = urlencode(
            {"email": "admin@example.com", "password": "admin-secret-1", "csrf": csrf}
        ).encode()
        response = handle_http(
            self.conn,
            "POST",
            "/admin/connexion",
            {"cookie": f"sid={sid}", "content-type": "application/x-www-form-urlencoded"},
            body,
        )
        sid = dict(response.headers)["Set-Cookie"].split("sid=", 1)[1].split(";", 1)[0]
        return sid

    def test_settings_has_eye_and_team_form(self):
        sid = self._admin_sid()
        page = handle_http(self.conn, "GET", "/admin/reglages", {"cookie": f"sid={sid}"}, b"")
        text = page.body.decode("utf-8")
        self.assertEqual(page.status, 200)
        self.assertIn("data-password-toggle", text)
        self.assertIn("Équipe", text)
        self.assertIn('action="/admin/equipe"', text)

    def test_add_driver_and_admin_to_team(self):
        create_staff(self.conn, "livreur2@example.com", "driver-secret-1", "Awa", role="driver")
        create_staff(self.conn, "chef@example.com", "admin-secret-2", "Chef", role="admin")
        roles = {
            row["email"]: row["role"]
            for row in self.conn.execute("SELECT email, role FROM users").fetchall()
        }
        self.assertEqual(roles["livreur2@example.com"], "driver")
        self.assertEqual(roles["chef@example.com"], "admin")


if __name__ == "__main__":
    unittest.main()
