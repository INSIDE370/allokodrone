import hashlib
import hmac
import json
import os
import unittest
from datetime import datetime

from app.auth import create_session
from app.cart import add_item
from app.catalog import product_by_slug
from app.db import init_db
from app.delivery import quote_delivery
from app.orders import place_order
from app.schedule import PARIS
from app.server import handle_http
from app.stripe_pay import refund_order
from app.uber_direct import handle_webhook, verify_signature
import app.delivery as delivery

TUESDAY_NOON = datetime(2026, 10, 20, 12, 30, tzinfo=PARIS)


class PlatformTests(unittest.TestCase):
    def setUp(self):
        import tempfile

        self.tmp = tempfile.TemporaryDirectory()
        self.conn = init_db(os.path.join(self.tmp.name, "shop.db"))
        from app.seed import seed

        seed(self.conn)
        self.sid = create_session(self.conn)
        self.conn.execute(
            "INSERT INTO payment_methods (code, label, active) VALUES ('pay_at_pickup', 'Au retrait', 1)"
        )
        self.conn.execute(
            "UPDATE products SET price_cents = 450, price_confirmed = 1 WHERE slug = 'alloko'"
        )
        delivery._transport = None

    def tearDown(self):
        delivery._transport = None
        self.conn.close()
        self.tmp.cleanup()

    def _distance_mode(self, meters=3000, fee=250):
        self.conn.execute(
            "INSERT INTO settings (key, value) VALUES ('delivery_mode', ?)",
            (json.dumps("distance"),),
        )
        self.conn.execute(
            "INSERT INTO distance_bands (max_meters, fee_cents, fee_confirmed, active) VALUES (?, ?, 1, 1)",
            (meters, fee),
        )

    def test_distance_fee_is_recalculated_and_client_amount_is_ignored(self):
        self._distance_mode()
        delivery._transport = lambda _address: (1800, None)
        product = product_by_slug(self.conn, "alloko")
        add_item(self.conn, self.sid, product["id"], [], 1)
        order, errors = place_order(
            self.conn,
            self.sid,
            None,
            {
                "idempotency_key": "dist-1",
                "nom": "Awa Diallo",
                "email": "awa@example.com",
                "telephone": "0612345678",
                "mode": "delivery",
                "rue": "10 rue des Lilas",
                "code_postal": "93130",
                "ville": "Noisy-le-Sec",
                "paiement": "pay_at_pickup",
                "frais": "1",
            },
            clock=TUESDAY_NOON,
        )
        self.assertEqual(errors, [])
        self.assertEqual(order["delivery_fee_cents"], 250)
        self.assertEqual(order["total_cents"], 700)
        self.assertEqual(order["distance_meters"], 1800)
        self.assertEqual(order["payment_status"], "unpaid")
        note = self.conn.execute("SELECT status, detail FROM notifications").fetchone()
        self.assertEqual(note["status"], "skipped")
        self.assertIn("Aucun fournisseur", note["detail"])

    def test_address_beyond_the_band_is_refused(self):
        self._distance_mode(meters=2000)
        quote, error = quote_delivery(
            self.conn,
            {"rue": "10 rue des Lilas", "code_postal": "75010", "ville": "Paris"},
            transport=lambda _address: (9000, None),
        )
        self.assertIsNone(quote)
        self.assertIn("Hors", error)

    def test_kilometers_return_the_open_band_price(self):
        from app.delivery import fee_for_km

        self._distance_mode(meters=10000, fee=1200)
        fee, error = fee_for_km(self.conn, "6,5")
        self.assertIsNone(error)
        self.assertEqual(fee, 1200)
        missing, error = fee_for_km(self.conn, "11")
        self.assertIsNone(missing)
        self.assertIn("Hors", error)

    def test_distance_without_map_key_is_refused(self):
        self._distance_mode()
        quote, error = quote_delivery(
            self.conn,
            {"rue": "10 rue des Lilas", "code_postal": "93130", "ville": "Noisy-le-Sec"},
        )
        self.assertIsNone(quote)
        self.assertIn("pas configuré", error)

    def test_deactivated_slot_cannot_be_booked(self):
        self.conn.execute(
            """
            INSERT INTO pickup_slots (slot_date, start_time, end_time, capacity, active)
            VALUES ('2026-10-20', '19:00', '19:15', 4, 0)
            """
        )
        slot = self.conn.execute("SELECT id FROM pickup_slots").fetchone()["id"]
        product = product_by_slug(self.conn, "alloko")
        add_item(self.conn, self.sid, product["id"], [], 1)
        _order, errors = place_order(
            self.conn,
            self.sid,
            None,
            {
                "idempotency_key": "slot-off",
                "nom": "Awa Diallo",
                "email": "awa@example.com",
                "telephone": "0612345678",
                "mode": "pickup",
                "slot_id": str(slot),
                "paiement": "pay_at_pickup",
            },
            clock=TUESDAY_NOON,
        )
        self.assertTrue(errors)

    def test_uber_webhook_rejects_a_bad_signature(self):
        os.environ["UBER_CLIENT_SECRET"] = "uber-test-secret"
        try:
            payload = b'{"id":"del_1","status":"delivered"}'
            status, body = handle_webhook(self.conn, payload, "deadbeef")
            self.assertEqual(status, 400)
            self.assertFalse(verify_signature(payload, "deadbeef"))
            good = hmac.new(b"uber-test-secret", payload, hashlib.sha256).hexdigest()
            self.assertTrue(verify_signature(payload, good))
            self.assertIn("invalide", body["error"])
        finally:
            os.environ.pop("UBER_CLIENT_SECRET", None)

    def test_stripe_refund_requires_a_confirmed_provider_refund(self):
        os.environ["STRIPE_SECRET_KEY"] = "sk_test_fixture_not_a_real_key"
        self.conn.execute(
            """
            INSERT INTO orders (
              public_ref, session_id, status, mode, customer_name, email, phone,
              payment_method, payment_status, subtotal_cents, delivery_fee_cents,
              discount_cents, total_cents, idempotency_key, snapshot_json, created_at,
              stripe_payment_intent
            ) VALUES (
              'AK-REFUND1', 'sess', 'completed', 'pickup', 'Awa', 'awa@example.com', '0612345678',
              'stripe', 'paid', 450, 0, 0, 450, 'refund-key', '[]', '2026-10-20T10:00:00+00:00', 'pi_test_1'
            )
            """
        )
        order = self.conn.execute("SELECT * FROM orders WHERE public_ref = 'AK-REFUND1'").fetchone()

        class Response:
            def __init__(self, payload):
                self.payload = json.dumps(payload).encode()

            def read(self):
                return self.payload

            def __enter__(self):
                return self

            def __exit__(self, *_args):
                return False

        import urllib.request

        original = urllib.request.urlopen
        urllib.request.urlopen = lambda *_args, **_kwargs: Response({"status": "pending"})
        try:
            error = refund_order(self.conn, order)
        finally:
            urllib.request.urlopen = original
            os.environ.pop("STRIPE_SECRET_KEY", None)
        self.assertIn("pas encore", error)
        row = self.conn.execute("SELECT payment_status FROM orders WHERE id = ?", (order["id"],)).fetchone()
        self.assertEqual(row["payment_status"], "paid")

    def test_zone_stays_closed_until_the_restaurant_confirms_the_fee(self):
        from app.admin_store import add_zone, set_zone_active

        self.assertIsNone(add_zone(self.conn, {"nom": "Noisy-le-Sec", "frais": "2,50", "active": "1"}))
        zone = self.conn.execute("SELECT * FROM delivery_zones").fetchone()
        self.assertEqual(zone["fee_confirmed"], 0)
        self.assertEqual(zone["active"], 0)
        error = set_zone_active(self.conn, zone["id"], True)
        self.assertIn("valid", error)
        self.conn.execute(
            "UPDATE delivery_zones SET fee_confirmed = 1 WHERE id = ?",
            (zone["id"],),
        )
        self.assertIsNone(set_zone_active(self.conn, zone["id"], True))
        opened = self.conn.execute("SELECT active FROM delivery_zones WHERE id = ?", (zone["id"],)).fetchone()
        self.assertEqual(opened["active"], 1)

    def test_confirming_a_zone_fee_keeps_it_closed(self):
        from app.admin_store import add_zone, confirm_zone_fee, set_zone_active

        self.assertIsNone(add_zone(self.conn, {"nom": "Paris", "frais": "13"}))
        zone = self.conn.execute("SELECT * FROM delivery_zones WHERE name = 'Paris'").fetchone()
        self.assertIsNone(confirm_zone_fee(self.conn, zone["id"]))
        saved = self.conn.execute("SELECT fee_confirmed, active FROM delivery_zones WHERE id = ?", (zone["id"],)).fetchone()
        self.assertEqual(saved["fee_confirmed"], 1)
        self.assertEqual(saved["active"], 0)
        self.assertIsNone(set_zone_active(self.conn, zone["id"], True))

    def test_opening_a_distance_band_publishes_its_fee(self):
        from app.admin_store import add_distance_band, set_band_active

        self.assertIsNone(add_distance_band(self.conn, {"km": "10", "frais": "12"}))
        band = self.conn.execute("SELECT * FROM distance_bands").fetchone()
        self.assertEqual(band["fee_confirmed"], 0)
        self.assertEqual(band["active"], 0)
        self.assertIsNone(set_band_active(self.conn, band["id"], True))
        saved = self.conn.execute(
            "SELECT fee_cents, fee_confirmed, active FROM distance_bands WHERE id = ?",
            (band["id"],),
        ).fetchone()
        self.assertEqual(saved["fee_cents"], 1200)
        self.assertEqual(saved["fee_confirmed"], 1)
        self.assertEqual(saved["active"], 1)

    def test_refused_map_key_is_not_stored(self):
        import json

        from app import delivery
        from app.admin_store import save_geo_key
        from app.delivery import geo_configured

        original = delivery.probe_key
        delivery.probe_key = lambda _key: "La clé OpenRouteService a été refusée."
        try:
            error = save_geo_key(self.conn, {"cle": "pas-une-cle-openrouteservice"})
        finally:
            delivery.probe_key = original
        self.assertIn("refusée", error)
        self.assertFalse(geo_configured(self.conn))
        self.conn.execute(
            "INSERT INTO settings (key, value) VALUES ('geo_api_key', ?)",
            (json.dumps("cle-enregistree-pour-le-test"),),
        )
        self.assertTrue(geo_configured(self.conn))

    def test_notification_counter_clears_when_the_list_is_opened(self):
        from app.notify import mark_seen, record, unseen_count

        self.assertEqual(unseen_count(self.conn), 0)
        self.assertEqual(record(self.conn, None, "order.placed"), "skipped")
        self.assertEqual(unseen_count(self.conn), 1)
        mark_seen(self.conn)
        self.assertEqual(unseen_count(self.conn), 0)

