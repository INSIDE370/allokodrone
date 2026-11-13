import os
import tempfile
import unittest
from datetime import datetime, timedelta, timezone

from app.auth import create_session, iso
from app.cart import add_item
from app.catalog import product_by_slug
from app.db import init_db
from app.kitchen import (
    average_prep_minutes,
    level_for,
    load_board,
    mark_line,
    mark_ready,
    render_kitchen,
    save_thresholds,
    thresholds,
)
from app.orders import set_status
from app.schedule import PARIS
from app.seed import seed

NOON = datetime(2026, 10, 20, 12, 30, tzinfo=PARIS)


class KitchenDisplayTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.conn = init_db(os.path.join(self.tmp.name, "shop.db"))
        seed(self.conn)
        self.sid = create_session(self.conn)
        self.conn.execute(
            """
            INSERT INTO pickup_slots (slot_date, start_time, end_time, capacity, active)
            VALUES ('2026-10-20', '19:00', '19:15', 4, 1)
            """
        )
        self.slot = self.conn.execute("SELECT id FROM pickup_slots").fetchone()["id"]
        os.environ["STRIPE_SECRET_KEY"] = "sk_test_fixture_not_a_real_key"
        self.conn.execute(
            "UPDATE products SET price_cents = 450, price_confirmed = 1 WHERE slug IN ('alloko', 'coca')"
        )

    def tearDown(self):
        os.environ.pop("STRIPE_SECRET_KEY", None)
        self.conn.close()
        self.tmp.cleanup()

    def order(self, slugs):
        for slug in slugs:
            product = product_by_slug(self.conn, slug)
            add_item(self.conn, self.sid, product["id"], [], 1)
        from app.orders import place_order

        order, errors = place_order(
            self.conn,
            self.sid,
            None,
            {
                "idempotency_key": "kds-" + "-".join(slugs),
                "nom": "Awa Diallo",
                "email": "awa@example.com",
                "telephone": "0612345678",
                "mode": "pickup",
                "slot_id": str(self.slot),
                "paiement": "stripe",
            },
            clock=NOON,
        )
        self.assertEqual(errors, [])
        self.conn.execute("UPDATE orders SET payment_status = 'paid' WHERE id = ?", (order["id"],))
        self.sid = create_session(self.conn)
        return order

    def test_a_future_pickup_stays_normal_and_a_late_one_is_urgent(self):
        limits = {"attention_minutes": 8, "urgent_minutes": 15}
        pickup = {
            "mode": "pickup",
            "slot_date": "2026-10-20",
            "start_time": "19:00",
            "created_at": iso(NOON.astimezone(timezone.utc)),
        }
        self.assertEqual(level_for(pickup, NOON, limits), "normal")
        self.assertEqual(level_for(pickup, NOON.replace(hour=19, minute=1), limits), "urgent")
        delivery = {
            "mode": "delivery",
            "created_at": iso(NOON.astimezone(timezone.utc)),
        }
        self.assertEqual(level_for(delivery, NOON + timedelta(minutes=20), limits), "urgent")
        self.assertEqual(level_for(delivery, NOON + timedelta(minutes=3), limits), "normal")

    def test_one_finished_dish_does_not_close_the_order(self):
        order = self.order(["alloko", "coca"])
        self.assertIsNone(set_status(self.conn, order["id"], "preparing"))
        self.assertIsNone(mark_line(self.conn, order["id"], 0, True, now=NOON))
        status = self.conn.execute("SELECT status FROM orders WHERE id = ?", (order["id"],)).fetchone()["status"]
        self.assertEqual(status, "preparing")
        self.assertIsNone(mark_line(self.conn, order["id"], 1, True, now=NOON))
        status = self.conn.execute("SELECT status FROM orders WHERE id = ?", (order["id"],)).fetchone()["status"]
        self.assertEqual(status, "ready")

    def test_ready_requires_confirmation_and_hides_finished_orders(self):
        order = self.order(["alloko"])
        self.assertEqual(mark_ready(self.conn, order["id"], "0"), "Confirmez que tous les postes ont fini.")
        self.assertEqual(self.conn.execute("SELECT status FROM orders WHERE id = ?", (order["id"],)).fetchone()["status"], "received")
        self.assertIsNone(set_status(self.conn, order["id"], "preparing"))
        self.assertIsNone(mark_ready(self.conn, order["id"], "1"))
        self.assertIsNone(set_status(self.conn, order["id"], "completed"))
        board = load_board(self.conn, {}, now=NOON)
        refs = [item["public_ref"] for _status, _title, group in board["columns"] for item in group]
        self.assertNotIn(order["public_ref"], refs)
        self.assertIsNotNone(average_prep_minutes(self.conn, datetime.now(PARIS)))

    def test_station_filter_and_search_use_real_orders(self):
        order = self.order(["alloko", "coca"])
        drinks = load_board(self.conn, {"poste": ["boissons"]}, now=NOON)
        cards = [item for _status, _title, group in drinks["columns"] for item in group]
        self.assertEqual([item["public_ref"] for item in cards], [order["public_ref"]])
        html = render_kitchen(type("Ctx", (), {"conn": self.conn, "session": {"csrf": "token"}})(), {"poste": ["boissons"]})
        self.assertIn("Coca", html)
        self.assertNotIn("Alloko", html)
        self.assertNotIn("allerg", html.lower())
        self.assertIn("hors de ce poste", html)
        missed = load_board(self.conn, {"q": ["ZZ-ABSENT"]}, now=NOON)
        self.assertEqual([item for _s, _t, group in missed["columns"] for item in group], [])

    def test_thresholds_stay_in_order(self):
        self.assertEqual(save_thresholds(self.conn, "10", "10"), "Le délai urgent doit être plus long que le délai d'attention.")
        self.assertIsNone(save_thresholds(self.conn, "10", "20"))
        self.assertEqual(thresholds(self.conn), {"attention_minutes": 10, "urgent_minutes": 20})
