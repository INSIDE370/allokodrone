import os
import tempfile
import unittest
from datetime import datetime

from app.auth import create_session, ensure_admin
from app.cart import add_item, cart_lines, set_promo
from app.catalog import product_by_slug
from app.db import init_db
from app.orders import place_order
from app.pricing import quote_product
from app.schedule import PARIS
from app.seed import seed
from app.server import handle_http
TUESDAY_NOON = datetime(2026, 10, 20, 12, 30, tzinfo=PARIS)
TUESDAY_MORNING = datetime(2026, 10, 20, 10, 0, tzinfo=PARIS)


class OrderingTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.db = os.path.join(self.tmp.name, "shop.db")
        self.conn = init_db(self.db)
        seed(self.conn)
        self.sid = create_session(self.conn)

    def tearDown(self):
        self.conn.close()
        self.tmp.cleanup()

    def choices(self, slug, picks):
        product = product_by_slug(self.conn, slug)
        rows = self.conn.execute(
            """
            SELECT ch.id, ch.name, g.name AS group_name
            FROM option_choices ch
            JOIN option_groups g ON g.id = ch.group_id
            WHERE g.product_id = ?
            """,
            (product["id"],),
        ).fetchall()
        ids = []
        for group, name in picks:
            match = next(row for row in rows if row["group_name"] == group and row["name"] == name)
            ids.append(match["id"])
        return product, ids

    def confirm_price(self, slug, cents):
        self.conn.execute(
            "UPDATE products SET price_cents = ?, price_confirmed = 1 WHERE slug = ?",
            (cents, slug),
        )

    def test_unpublished_price_blocks_add(self):
        product = product_by_slug(self.conn, "salade-berbere")
        quote = add_item(self.conn, self.sid, product["id"], [], 1)
        self.assertTrue(quote.issues)
        _cart, lines = cart_lines(self.conn, self.sid)
        self.assertEqual(lines, [])

    def test_bowl_requires_choices_and_prices_jollof(self):
        product, _ids = self.choices("bowl", [])
        quote = quote_product(self.conn, product["id"], [], 1)
        self.assertFalse(quote.ok)
        self.confirm_price("bowl", 1200)
        _product, ids = self.choices(
            "bowl",
            [("Base", "Riz Jollof"), ("Viande", "Poulet effiloché"), ("Sauce", "Yassa"), ("Side", "Alloko")],
        )
        quote = quote_product(self.conn, product["id"], ids, 2)
        self.assertTrue(quote.ok)
        self.assertEqual(quote.unit_cents, 1300)
        self.assertEqual(quote.line_cents, 2600)

    def test_different_customizations_stay_distinct(self):
        self.confirm_price("bowl", 1000)
        _product, jollof = self.choices(
            "bowl",
            [("Base", "Riz Jollof"), ("Viande", "Poulet effiloché"), ("Sauce", "Yassa"), ("Side", "Alloko")],
        )
        _product, blanc = self.choices(
            "bowl",
            [("Base", "Riz blanc"), ("Viande", "Poulet effiloché"), ("Sauce", "Yassa"), ("Side", "Alloko")],
        )
        product = product_by_slug(self.conn, "bowl")
        add_item(self.conn, self.sid, product["id"], jollof, 1)
        add_item(self.conn, self.sid, product["id"], blanc, 1)
        add_item(self.conn, self.sid, product["id"], blanc, 1)
        _cart, lines = cart_lines(self.conn, self.sid)
        self.assertEqual(len(lines), 2)
        quantities = sorted(item["quantity"] for item, _quote in lines)
        self.assertEqual(quantities, [1, 2])

    def test_order_rejected_without_payment_zone_and_slot(self):
        self.confirm_price("alloko", 400)
        product = product_by_slug(self.conn, "alloko")
        add_item(self.conn, self.sid, product["id"], [], 1)
        _order, errors = place_order(
            self.conn,
            self.sid,
            None,
            {
                "idempotency_key": "key-1",
                "nom": "Awa Diallo",
                "email": "awa@example.com",
                "telephone": "0612345678",
                "mode": "delivery",
                "rue": "10 rue des Lilas",
                "code_postal": "93130",
                "ville": "Noisy-le-Sec",
            },
            clock=TUESDAY_NOON,
        )
        self.assertIsNone(_order)
        self.assertTrue(any("zone" in error or "reglement" in error for error in errors))

    def test_pickup_requires_card_and_is_idempotent(self):
        self.confirm_price("alloko", 450)
        product = product_by_slug(self.conn, "alloko")
        add_item(self.conn, self.sid, product["id"], [], 2)
        self.conn.execute(
            "INSERT INTO payment_methods (code, label, active) VALUES ('pay_at_pickup', 'Au retrait', 1)"
        )
        self.conn.execute(
            """
            INSERT INTO pickup_slots (slot_date, start_time, end_time, capacity, active)
            VALUES ('2026-10-20', '19:00', '19:15', 1, 1)
            """
        )
        slot_id = self.conn.execute("SELECT id FROM pickup_slots").fetchone()["id"]
        form = {
            "idempotency_key": "same-key",
            "nom": "Awa Diallo",
            "email": "awa@example.com",
            "telephone": "0612345678",
            "mode": "pickup",
            "slot_id": str(slot_id),
            "paiement": "pay_at_pickup",
        }
        refused, errors = place_order(self.conn, self.sid, None, form, clock=TUESDAY_NOON)
        self.assertIsNone(refused)
        self.assertTrue(any("carte" in error.lower() for error in errors))
        os.environ["STRIPE_SECRET_KEY"] = "sk_test_fixture_not_a_real_key"
        try:
            form["paiement"] = "stripe"
            order, errors = place_order(self.conn, self.sid, None, form, clock=TUESDAY_NOON)
            self.assertEqual(errors, [])
            self.assertEqual(order["payment_status"], "pending")
            self.assertEqual(order["payment_method"], "stripe")
            self.assertEqual(order["total_cents"], 900)
            self.assertEqual(order["status"], "received")
            again, errors = place_order(self.conn, self.sid, None, form, clock=TUESDAY_NOON)
            self.assertEqual(errors, [])
            self.assertEqual(again["id"], order["id"])
            count = self.conn.execute("SELECT COUNT(*) AS n FROM orders").fetchone()["n"]
            self.assertEqual(count, 1)
        finally:
            os.environ.pop("STRIPE_SECRET_KEY", None)

    def test_unknown_promo_does_not_block_card_payment(self):
        self.confirm_price("alloko", 450)
        product = product_by_slug(self.conn, "alloko")
        add_item(self.conn, self.sid, product["id"], [], 1)
        set_promo(self.conn, self.sid, "INCONNU")
        self.conn.execute(
            """
            INSERT INTO pickup_slots (slot_date, start_time, end_time, capacity, active)
            VALUES ('2026-10-20', '19:00', '19:15', 1, 1)
            """
        )
        slot_id = self.conn.execute("SELECT id FROM pickup_slots").fetchone()["id"]
        os.environ["STRIPE_SECRET_KEY"] = "sk_test_fixture_not_a_real_key"
        try:
            order, errors = place_order(
                self.conn,
                self.sid,
                None,
                {
                    "idempotency_key": "promo-ignored",
                    "nom": "Awa Diallo",
                    "email": "awa@example.com",
                    "telephone": "0612345678",
                    "mode": "pickup",
                    "slot_id": str(slot_id),
                    "paiement": "stripe",
                },
                clock=TUESDAY_NOON,
            )
            self.assertEqual(errors, [])
            self.assertEqual(order["discount_cents"], 0)
            self.assertEqual(order["total_cents"], 450)
            self.assertIsNone(order["promo_code"])
        finally:
            os.environ.pop("STRIPE_SECRET_KEY", None)

    def test_slot_capacity_and_closed_delivery(self):
        self.confirm_price("alloko", 450)
        product = product_by_slug(self.conn, "alloko")
        self.conn.execute(
            "INSERT INTO payment_methods (code, label, active) VALUES ('pay_on_delivery', 'Livraison', 1)"
        )
        self.conn.execute(
            """
            INSERT INTO delivery_zones (name, fee_cents, fee_confirmed, active)
            VALUES ('Noisy-le-Sec', 250, 1, 1)
            """
        )
        zone_id = self.conn.execute("SELECT id FROM delivery_zones").fetchone()["id"]
        add_item(self.conn, self.sid, product["id"], [], 1)
        _order, errors = place_order(
            self.conn,
            self.sid,
            None,
            {
                "idempotency_key": "closed",
                "nom": "Awa Diallo",
                "email": "awa@example.com",
                "telephone": "0612345678",
                "mode": "delivery",
                "zone_id": str(zone_id),
                "rue": "10 rue des Lilas",
                "code_postal": "93130",
                "ville": "Noisy-le-Sec",
                "paiement": "pay_on_delivery",
            },
            clock=TUESDAY_MORNING,
        )
        self.assertIsNone(_order)
        self.assertTrue(any("livraison" in error.lower() for error in errors))

    def test_client_cannot_open_admin_and_csrf_is_required(self):
        ensure_admin(self.conn, "owner@allokodrone.fr", "motdepasse-solide")
        response = handle_http(self.conn, "GET", "/admin", {}, b"")
        self.assertEqual(response.status, 303)
        self.assertIn("/admin/connexion", dict(response.headers)["Location"])
        session = self.conn.execute("SELECT * FROM sessions").fetchone()
        user = self.conn.execute(
            """
            INSERT INTO users (email, password_hash, name, phone, role, created_at)
            VALUES ('client@example.com', 'x', 'Client', '', 'customer', '2026-10-20T10:00:00+00:00')
            """
        )
        self.conn.execute("UPDATE sessions SET user_id = ? WHERE id = ?", (user.lastrowid, session["id"]))
        denied = handle_http(
            self.conn,
            "GET",
            "/admin/produits",
            {"cookie": f"sid={session['id']}"},
            b"",
        )
        self.assertEqual(denied.status, 403)
        forged = handle_http(
            self.conn,
            "POST",
            "/panier/ajouter",
            {"cookie": f"sid={session['id']}"},
            b"produit=1&quantite=1&csrf=faux",
        )
        self.assertEqual(forged.status, 400)

    def test_full_slot_rejects_a_second_order(self):
        self.confirm_price("alloko", 450)
        product = product_by_slug(self.conn, "alloko")
        self.conn.execute(
            """
            INSERT INTO pickup_slots (slot_date, start_time, end_time, capacity, active)
            VALUES ('2026-10-20', '19:00', '19:15', 1, 1)
            """
        )
        slot_id = self.conn.execute("SELECT id FROM pickup_slots").fetchone()["id"]
        form = {
            "nom": "Awa Diallo",
            "email": "awa@example.com",
            "telephone": "0612345678",
            "mode": "pickup",
            "slot_id": str(slot_id),
            "paiement": "stripe",
        }
        os.environ["STRIPE_SECRET_KEY"] = "sk_test_fixture_not_a_real_key"
        try:
            add_item(self.conn, self.sid, product["id"], [], 1)
            first, errors = place_order(self.conn, self.sid, None, {**form, "idempotency_key": "one"}, clock=TUESDAY_NOON)
            self.assertEqual(errors, [])
            other = create_session(self.conn)
            add_item(self.conn, other, product["id"], [], 1)
            second, errors = place_order(self.conn, other, None, {**form, "idempotency_key": "two"}, clock=TUESDAY_NOON)
            self.assertIsNone(second)
            self.assertTrue(any("creneau" in error.lower() for error in errors))
            self.assertEqual(first["payment_status"], "pending")
        finally:
            os.environ.pop("STRIPE_SECRET_KEY", None)

    def test_midi_formula_is_blocked_outside_its_window(self):
        product = product_by_slug(self.conn, "midi-bowl")
        quote = quote_product(self.conn, product["id"], [], 1, clock=TUESDAY_NOON)
        self.assertFalse(quote.ok)
        self.assertTrue(any("valider" in issue.lower() or "commandable" in issue.lower() or "Formule" in issue for issue in quote.issues))
        sunday = datetime(2026, 10, 25, 12, 30, tzinfo=PARIS)
        self.conn.execute(
            "UPDATE products SET price_cents = 900, price_confirmed = 1, orderable = 1, block_reason = NULL WHERE slug = 'midi-bowl'"
        )
        quote = quote_product(self.conn, product["id"], [], 1, clock=sunday)
        self.assertTrue(any("midi" in issue.lower() for issue in quote.issues))

    def test_home_and_menu_render_real_products(self):
        import json

        response = handle_http(self.conn, "GET", "/api/catalogue?q=Yassa", {}, b"")
        text = response.body.decode("utf-8")
        data = json.loads(text)
        self.assertEqual(response.status, 200)
        self.assertTrue(any("Pulled Beef Yassa" in item["name"] for item in data["products"]))
        priced = next(item for item in data["products"] if "Pulled Beef Yassa" in item["name"])
        self.assertEqual(priced["priceLabel"], "13,90 €")
        self.assertNotIn("12,50", text)

    def test_api_refuses_unpriced_add(self):
        import json

        opened = handle_http(self.conn, "GET", "/api/session", {}, b"")
        session = json.loads(opened.body)
        cookie = dict(opened.headers)["Set-Cookie"].split(";", 1)[0]
        product = product_by_slug(self.conn, "salade-berbere")
        denied = handle_http(
            self.conn,
            "POST",
            "/api/panier/ajouter",
            {"cookie": cookie, "content-type": "application/json", "x-csrf": session["csrf"]},
            json.dumps({"produit": product["id"], "quantite": 1, "choix": []}).encode(),
        )
        self.assertEqual(denied.status, 422)
        self.assertIn("valide", denied.body.decode("utf-8").lower())

    def test_order_pdf_is_limited_to_its_session(self):
        self.confirm_price("alloko", 450)
        product = product_by_slug(self.conn, "alloko")
        self.conn.execute(
            """
            INSERT INTO pickup_slots (slot_date, start_time, end_time, capacity, active)
            VALUES ('2026-10-20', '19:00', '19:15', 2, 1)
            """
        )
        slot_id = self.conn.execute("SELECT id FROM pickup_slots").fetchone()["id"]
        add_item(self.conn, self.sid, product["id"], [], 1)
        os.environ["STRIPE_SECRET_KEY"] = "sk_test_fixture_not_a_real_key"
        try:
            order, errors = place_order(
                self.conn,
                self.sid,
                None,
                {
                    "nom": "Awa Diallo",
                    "email": "awa@example.com",
                    "telephone": "0612345678",
                    "mode": "pickup",
                    "slot_id": str(slot_id),
                    "paiement": "stripe",
                    "idempotency_key": "pdf-1",
                },
                clock=TUESDAY_NOON,
            )
        finally:
            os.environ.pop("STRIPE_SECRET_KEY", None)
        self.assertEqual(errors, [])
        owned = handle_http(
            self.conn,
            "GET",
            f"/api/commande/{order['public_ref']}/pdf",
            {"cookie": f"sid={self.sid}"},
            b"",
        )
        self.assertEqual(owned.status, 200)
        self.assertEqual(owned.content_type, "application/pdf")
        self.assertTrue(owned.body.startswith(b"%PDF"))
        self.assertIn(order["public_ref"].encode(), owned.body)
        self.assertIn(b"Awa Diallo", owned.body)
        self.assertIn(b"4,50", owned.body)
        self.assertIn(b"Alloko", owned.body)
        self.assertIn(b"0.769 0.318 0.165", owned.body)
        disposition = dict(owned.headers)["Content-Disposition"]
        self.assertIn(order["public_ref"], disposition)
        stranger = handle_http(
            self.conn,
            "GET",
            f"/api/commande/{order['public_ref']}/pdf",
            {"cookie": f"sid={create_session(self.conn)}"},
            b"",
        )
        self.assertEqual(stranger.status, 404)

    def test_completed_order_can_publish_one_verified_review(self):
        import json

        from app.orders import set_status

        opened = handle_http(self.conn, "GET", "/api/session", {}, b"")
        session = json.loads(opened.body)
        cookie = dict(opened.headers)["Set-Cookie"].split(";", 1)[0]
        sid = cookie.split("=", 1)[1]
        listed = handle_http(self.conn, "GET", "/api/avis", {"cookie": cookie}, b"")
        board = json.loads(listed.body)
        self.assertEqual(listed.status, 200)
        self.assertIn("pulled beef yassa", board["google"]["quote"])
        self.assertEqual(board["reviews"], [])
        self.assertIsNone(board["average"])
        refused = handle_http(
            self.conn,
            "POST",
            "/api/avis",
            {"cookie": cookie, "content-type": "application/json", "x-csrf": session["csrf"]},
            json.dumps({"nom": "Awa", "note": 4, "message": "Le yassa était très bon."}).encode(),
        )
        self.assertEqual(refused.status, 422)
        self.confirm_price("alloko", 490)
        product = product_by_slug(self.conn, "alloko")
        add_item(self.conn, sid, product["id"], [], 1)
        self.conn.execute(
            """
            INSERT INTO pickup_slots (slot_date, start_time, end_time, capacity, active)
            VALUES ('2026-10-20', '19:00', '19:15', 2, 1)
            """
        )
        slot_id = self.conn.execute("SELECT id FROM pickup_slots ORDER BY id DESC").fetchone()["id"]
        os.environ["STRIPE_SECRET_KEY"] = "sk_test_fixture_not_a_real_key"
        try:
            order, errors = place_order(
                self.conn,
                sid,
                None,
                {
                    "idempotency_key": "review-order",
                    "nom": "Awa Diallo",
                    "email": "awa@example.com",
                    "telephone": "0612345678",
                    "mode": "pickup",
                    "slot_id": str(slot_id),
                    "paiement": "stripe",
                },
                clock=TUESDAY_NOON,
            )
            self.assertEqual(errors, [])
        finally:
            os.environ.pop("STRIPE_SECRET_KEY", None)
        still = handle_http(
            self.conn,
            "POST",
            "/api/avis",
            {"cookie": cookie, "content-type": "application/json", "x-csrf": session["csrf"]},
            json.dumps(
                {
                    "orderRef": order["public_ref"],
                    "nom": "Awa",
                    "note": 4,
                    "message": "Le yassa était très bon.",
                }
            ).encode(),
        )
        self.assertEqual(still.status, 422)
        self.conn.execute("UPDATE orders SET payment_status = 'paid' WHERE id = ?", (order["id"],))
        self.assertIsNone(set_status(self.conn, order["id"], "completed"))
        posted = handle_http(
            self.conn,
            "POST",
            "/api/avis",
            {"cookie": cookie, "content-type": "application/json", "x-csrf": session["csrf"]},
            json.dumps(
                {
                    "orderRef": order["public_ref"],
                    "nom": "Awa",
                    "note": 5,
                    "message": "Le yassa était excellent, service rapide.",
                    "notePlats": 5,
                    "noteService": 4,
                }
            ).encode(),
        )
        data = json.loads(posted.body)
        self.assertEqual(posted.status, 200)
        self.assertEqual(data["count"], 1)
        self.assertEqual(data["average"], 5)
        self.assertEqual(data["reviews"][0]["author"], "Awa")
        self.assertEqual(data["reviews"][0]["stars"], 5)
        self.assertTrue(data["reviews"][0]["verified"])
        again = handle_http(
            self.conn,
            "POST",
            "/api/avis",
            {"cookie": cookie, "content-type": "application/json", "x-csrf": session["csrf"]},
            json.dumps(
                {
                    "orderRef": order["public_ref"],
                    "nom": "Awa",
                    "note": 3,
                    "message": "Deuxième avis interdit.",
                }
            ).encode(),
        )
        self.assertEqual(again.status, 422)
        useful = handle_http(
            self.conn,
            "POST",
            f"/api/avis/{data['reviews'][0]['id']}/utile",
            {"cookie": cookie, "content-type": "application/json", "x-csrf": session["csrf"]},
            b"{}",
        )
        self.assertEqual(useful.status, 200)
        self.assertEqual(json.loads(useful.body)["usefulCount"], 1)


if __name__ == "__main__":
    unittest.main()
