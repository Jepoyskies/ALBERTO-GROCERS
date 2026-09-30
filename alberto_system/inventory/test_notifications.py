"""
Regression tests for the navbar dark-mode toggle and the notification bell.

These exist because both features were originally pure decoration in the
template (a button with no handler, a badge hardcoded to "1"). Nothing caught
that, so the hooks are now asserted explicitly:

* the notification bell is driven by ``core.context_processors.notifications``
  against real ``Product`` data, so the badge can never be a literal again;
* the theme is switched client-side, so we can only assert the hooks the
  JavaScript depends on still exist. Losing one of these fails the build rather
  than silently leaving a dead button in the UI.
"""

import re

from django.contrib.auth.models import Permission, User
from django.test import Client, RequestFactory, TestCase

from core.context_processors import notifications
from .models import Product


def _view_product_perm():
    return Permission.objects.get(
        codename="view_product", content_type__app_label="inventory"
    )


class NotificationContextProcessorTests(TestCase):
    """The navbar bell is fed by core.context_processors.notifications."""

    def setUp(self):
        self.user = User.objects.create_user(
            username="notif_tester", password="pw12345", is_staff=True
        )
        # Without view_product the processor deliberately returns nothing.
        self.user.user_permissions.add(_view_product_perm())
        self.factory = RequestFactory()

        self.low = Product.objects.create(
            name="Low Item", sku="N-LOW", price=10, quantity=2, reorder_level=10
        )
        self.out = Product.objects.create(
            name="Out Item", sku="N-OUT", price=10, quantity=0, reorder_level=5
        )
        self.ok = Product.objects.create(
            name="Healthy Item", sku="N-OK", price=10, quantity=99, reorder_level=5
        )
        self.deactivated = Product.objects.create(
            name="Deactivated Low", sku="N-DEACT", price=10, quantity=1,
            reorder_level=5, status=Product.Status.DEACTIVATED,
        )

    def _run(self, user=None):
        # Set request.user explicitly rather than relying on RequestFactory's
        # `user=` kwarg, which is not consistent across Django versions.
        request = self.factory.get("/")
        request.user = self.user if user is None else user
        return notifications(request)

    def test_counts_active_low_stock(self):
        # Out-of-stock must be included: for an alert feed a product at zero is
        # the most urgent thing on the list, not something to omit.
        self.assertEqual(self._run()["notif_count"], 2)

    def test_excludes_healthy_and_deactivated(self):
        names = [p.name for p in self._run()["notif_items"]]
        self.assertIn("Low Item", names)
        self.assertIn("Out Item", names)
        self.assertNotIn("Healthy Item", names)
        self.assertNotIn("Deactivated Low", names)

    def test_anonymous_gets_no_notifications(self):
        from django.contrib.auth.models import AnonymousUser
        self.assertEqual(self._run(user=AnonymousUser()), {})

    def test_user_without_permission_gets_nothing(self):
        plain = User.objects.create_user(username="plain", password="pw12345")
        result = self._run(user=plain)
        self.assertEqual(result, {}, "product data must not leak to restricted users")

    def test_healthy_catalogue_reports_zero(self):
        Product.objects.all().delete()
        result = self._run()
        self.assertEqual(result["notif_count"], 0)
        self.assertEqual(result["notif_items"], [])

    def test_list_is_capped_but_count_is_accurate(self):
        Product.objects.filter(name="Healthy Item").delete()
        for i in range(12):
            Product.objects.create(
                name=f"Bulk {i}", sku=f"BULK-{i}", price=1, quantity=1, reorder_level=5
            )
        result = self._run()
        self.assertEqual(result["notif_count"], 14)
        self.assertEqual(len(result["notif_items"]), 8, "dropdown list is capped at 8")
        self.assertEqual(result["notif_extra"], 6)


class NavbarMarkupTests(TestCase):
    """Guards the template hooks the toggle and bell depend on."""

    def setUp(self):
        self.user = User.objects.create_user(
            username="markup_tester", password="pw12345"
        )
        self.user.user_permissions.add(_view_product_perm())

    def _dashboard_html(self):
        client = Client()
        client.force_login(self.user)
        response = client.get("/dashboard/")
        self.assertEqual(response.status_code, 200)
        return response.content.decode()

    def test_theme_hooks_present(self):
        html = self._dashboard_html()
        self.assertIn('data-bs-theme="light"', html)
        self.assertIn("albertoTheme", html)             # localStorage key + pre-paint script
        self.assertIn('id="themeToggleBtn"', html)
        self.assertIn('id="themeToggleLabel"', html)
        self.assertIn('[data-bs-theme="dark"]', html)   # dark palette block

    def test_bell_present_for_authenticated_user(self):
        html = self._dashboard_html()
        self.assertIn('id="notifBellBtn"', html)
        self.assertIn("notif-dropdown", html)

    def test_bell_hidden_from_anonymous_users(self):
        html = Client().get("/accounts/login/").content.decode()
        self.assertNotIn('id="notifBellBtn"', html)

    def test_badge_shows_real_count_not_a_literal(self):
        """Regression: the badge used to be a hardcoded '1' in the template."""
        Product.objects.create(
            name="Badge Item", sku="BADGE-1", price=5, quantity=1, reorder_level=4
        )
        Product.objects.create(
            name="Badge Item Two", sku="BADGE-2", price=5, quantity=2, reorder_level=4
        )
        html = self._dashboard_html()

        self.assertIn('id="notifBadge"', html)
        # The badge body must be the real count (2), rendered from the context
        # processor - not the literal 1 that used to be hardcoded in the template.
        match = re.search(r'id="notifBadge".*?>(.*?)</span>', html, re.S)
        self.assertIsNotNone(match, "badge span not found")
        self.assertEqual(match.group(1).strip(), "2")

        # The matching rows must be listed in the dropdown.
        self.assertIn("Badge Item", html)
        self.assertIn("Badge Item Two", html)

    def test_badge_hidden_when_nothing_is_low(self):
        html = self._dashboard_html()
        match = re.search(r'id="notifBadge"([^>]*)>(.*?)</span>', html, re.S)
        self.assertIsNotNone(match)
        self.assertIn("hidden", match.group(1), "empty badge must be hidden")
        self.assertEqual(match.group(2).strip(), "")
