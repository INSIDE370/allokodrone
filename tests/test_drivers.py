import os
import tempfile
import unittest
from datetime import datetime

from app.auth import create_session
from app.cart import add_item
from app.catalog import product_by_slug
from app.db import init_db
from app.drivers import accept_order, board, complete_order, release_order
from app.orders import place_order, set_status
from app.schedule import PARIS
from app.seed import seed

TUESDAY_NOON = datetime(2026, 10, 20, 12, 30, tzinfo=PARIS)


class DriverBoardTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.conn = init_db(os.path.join(self.tmp.name, "shop.db"))
        seed(self.conn)
        self.sid = create_session(self.conn)
        self.conn.execute(
            "UPDATE products SET price_cents = 450, price_confirmed = 1 WHERE slug = 'alloko'"
        )
        self.conn.execute(
            """
            INSERT INTO payment_methods (code, label, active)
            VALUES ('pay_on_delivery', 'Livraison', 1)
            ON CONFLICT(code) DO UPDATE SET active = 1
            """
        )
        self.conn.execute(
            """
            INSERT INTO delivery_zones (name, fee_cents, fee_confirmed, active)
            VALUES ('Noisy-le-Sec', 250, 1, 1)
            """
        )
        self.zone = self.conn.execute("SELECT id FROM delivery_zones").fetchone()["id"]
        self.conn.execute(
            """
            INSERT INTO settings (key, value) VALUES ('delivery_mode', ?)
            ON CONFLICT(key) DO UPDATE SET value = excluded.value
            """,
            ('"zones"',),
        )

    def tearDown(self):
        self.conn.close()
        self.tmp.cleanup()

    def _order(self):
        product = product_by_slug(self.conn, "alloko")
        add_item(self.conn, self.sid, product["id"], [], 1)
        order, errors = place_order(
            self.conn,
            self.sid,
            None,
            {
                "idempotency_key": "driver-1",
                "nom": "Awa Diallo",
                "email": "awa@example.com",
                "telephone": "0612345678",
                "mode": "delivery",
                "zone_id": str(self.zone),
                "rue": "10 rue de la République",
                "code_postal": "93130",
                "ville": "Noisy-le-Sec",
                "paiement": "pay_on_delivery",
            },
            clock=TUESDAY_NOON,
        )
        self.assertEqual(errors, [])
        set_status(self.conn, order["id"], "ready")
        return self.conn.execute("SELECT * FROM orders WHERE id = ?", (order["id"],)).fetchone()

    def test_accept_call_and_complete(self):
        order = self._order()
        data = board(self.conn)
        self.assertEqual(len(data["waiting"]), 1)
        error = accept_order(self.conn, order["id"], "Moussa", "0600000000")
        self.assertIsNone(error)
        fresh = self.conn.execute("SELECT * FROM orders WHERE id = ?", (order["id"],)).fetchone()
        self.assertEqual(fresh["status"], "out_for_delivery")
        self.assertEqual(fresh["driver_name"], "Moussa")
        data = board(self.conn)
        self.assertEqual(len(data["waiting"]), 0)
        self.assertEqual(len(data["active"]), 1)
        error = complete_order(self.conn, order["id"])
        self.assertIsNone(error)
        data = board(self.conn)
        self.assertEqual(len(data["active"]), 0)
        self.assertEqual(len(data["done"]), 1)

    def test_release_returns_to_waiting(self):
        order = self._order()
        accept_order(self.conn, order["id"], "Awa")
        error = release_order(self.conn, order["id"])
        self.assertIsNone(error)
        fresh = self.conn.execute("SELECT * FROM orders WHERE id = ?", (order["id"],)).fetchone()
        self.assertEqual(fresh["status"], "ready")
        self.assertFalse(fresh["driver_name"])
        self.assertEqual(len(board(self.conn)["waiting"]), 1)


if __name__ == "__main__":
    unittest.main()
