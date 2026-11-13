import os
import tempfile
import unittest
from urllib.parse import urlencode

from app.auth import create_driver, ensure_admin
from app.db import init_db
from app.seed import seed
from app.server import handle_http


class DriverAccessTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.db = os.path.join(self.tmp.name, "shop.db")
        self.conn = init_db(self.db)
        seed(self.conn)
        ensure_admin(self.conn, "admin@example.com", "admin-secret-1")
        create_driver(self.conn, "livreur@example.com", "driver-secret-1", "Moussa", "0600112233")
        self.conn.commit()

    def tearDown(self):
        self.conn.close()
        self.tmp.cleanup()

    def _login(self, email, password):
        opened = handle_http(self.conn, "GET", "/admin/connexion", {}, b"")
        cookie = dict(opened.headers).get("Set-Cookie", "")
        sid = cookie.split("sid=", 1)[1].split(";", 1)[0]
        csrf = self.conn.execute("SELECT csrf FROM sessions WHERE id = ?", (sid,)).fetchone()["csrf"]
        body = urlencode({"email": email, "password": password, "csrf": csrf}).encode()
        response = handle_http(
            self.conn,
            "POST",
            "/admin/connexion",
            {"cookie": f"sid={sid}", "content-type": "application/x-www-form-urlencoded"},
            body,
        )
        location = dict(response.headers).get("Location", "")
        set_cookie = dict(response.headers).get("Set-Cookie", "")
        if "sid=" in set_cookie:
            sid = set_cookie.split("sid=", 1)[1].split(";", 1)[0]
        return response, sid, location

    def test_driver_lands_on_courses_and_cannot_open_dashboard(self):
        response, sid, location = self._login("livreur@example.com", "driver-secret-1")
        self.assertEqual(response.status, 303)
        self.assertEqual(location, "/admin/livreurs")
        board = handle_http(self.conn, "GET", "/admin/livreurs", {"cookie": f"sid={sid}"}, b"")
        self.assertEqual(board.status, 200)
        text = board.body.decode("utf-8")
        self.assertIn("Mes courses", text)
        self.assertNotIn("Tableau de bord", text)
        self.assertNotIn(">Réglages<", text)
        blocked = handle_http(self.conn, "GET", "/admin", {"cookie": f"sid={sid}"}, b"")
        self.assertEqual(blocked.status, 303)
        self.assertEqual(dict(blocked.headers)["Location"], "/admin/livreurs")
        settings = handle_http(self.conn, "GET", "/admin/reglages", {"cookie": f"sid={sid}"}, b"")
        self.assertEqual(settings.status, 303)
        self.assertEqual(dict(settings.headers)["Location"], "/admin/livreurs")

    def test_admin_still_sees_full_nav_including_livreurs(self):
        _, sid, location = self._login("admin@example.com", "admin-secret-1")
        self.assertEqual(location, "/admin")
        home = handle_http(self.conn, "GET", "/admin", {"cookie": f"sid={sid}"}, b"")
        self.assertEqual(home.status, 200)
        text = home.body.decode("utf-8")
        self.assertIn("Tableau de bord", text)
        board = handle_http(self.conn, "GET", "/admin/livreurs", {"cookie": f"sid={sid}"}, b"")
        self.assertEqual(board.status, 200)
        board_text = board.body.decode("utf-8")
        self.assertIn("Livreurs", board_text)
        self.assertIn(">Réglages<", board_text)


if __name__ == "__main__":
    unittest.main()
