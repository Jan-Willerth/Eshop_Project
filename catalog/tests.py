from decimal import Decimal
from django.test import TestCase, Client
from django.urls import reverse
from catalog.models import Category, Product, VatRate


# ===================== CART TESTS =====================
class CartViewsTestCase(TestCase):
    """Test suite for cart functional logic, forms, and view behaviors."""

    def setUp(self) -> None:
        """Set up initial database fixtures for cart unit tests."""
        self.client = Client()

        # Create base VAT rate fixture
        self.vat_standard = VatRate.objects.create(
            label='21%',
            rate=Decimal('21.00'),
            is_active=True
        )

        # Create category fixture
        self.category = Category.objects.create(
            name='Filamenty',
            slug='filamenty',
            is_active=True
        )

        # Create primary product fixture (physical stock: 5 units)
        self.product_limited = Product.objects.create(
            name='Spectrum PLA – bílá',
            slug='spectrum-pla-bila',
            price_net=Decimal('450.00'),
            vat_rate=self.vat_standard,
            category=self.category,
            stock=5,
            is_active=True
        )

        # Create secondary product fixture for multi-item cart testing
        self.product_secondary = Product.objects.create(
            name='Spectrum PETG – černá',
            slug='spectrum-petg-cerna',
            price_net=Decimal('520.00'),
            vat_rate=self.vat_standard,
            category=self.category,
            stock=10,
            is_active=True
        )

    # ===================== BASIC CART OPERATIONS =====================
    def test_add_to_cart_successful(self) -> None:
        """Verify adding a valid item quantity to the cart session."""
        url = reverse('catalog:add_to_cart', args=[self.product_limited.id])
        response = self.client.post(url, {'quantity': 2})

        self.assertEqual(response.status_code, 302)
        session_cart = self.client.session.get('cart', {})
        self.assertIn(str(self.product_limited.id), session_cart)
        self.assertEqual(session_cart[str(self.product_limited.id)], 2)

    def test_add_to_cart_overstock_without_confirmation(self) -> None:
        """Adding more than stock without confirmation should fail and leave cart unchanged."""
        url = reverse('catalog:add_to_cart', args=[self.product_limited.id])
        response = self.client.post(url, {'quantity': 15})

        self.assertEqual(response.status_code, 302)
        self.assertIn(reverse('catalog:product_detail', args=[self.product_limited.slug]), response.url)

        session_cart = self.client.session.get('cart', {})
        self.assertNotIn(str(self.product_limited.id), session_cart)

    def test_add_to_cart_overstock_with_confirmation(self) -> None:
        """Overstock with confirmed checkbox should succeed."""
        url = reverse('catalog:add_to_cart', args=[self.product_limited.id])
        response = self.client.post(url, {
            'quantity': 15,
            'overstock_confirmed': True
        })

        self.assertEqual(response.status_code, 302)
        session_cart = self.client.session.get('cart', {})
        self.assertIn(str(self.product_limited.id), session_cart)
        self.assertEqual(session_cart[str(self.product_limited.id)], 15)

    def test_update_cart_quantity_override(self) -> None:
        """Verify cart update directly overrides existing quantity instead of adding to it."""
        session = self.client.session
        session['cart'] = {str(self.product_limited.id): 3}
        session.save()

        url = reverse('catalog:add_to_cart', args=[self.product_limited.id])
        self.client.post(url, {
            'quantity': 7,
            'override': 'on',
            'overstock_confirmed': True
        })

        session_cart = self.client.session.get('cart', {})
        self.assertEqual(session_cart[str(self.product_limited.id)], 7)

    def test_remove_from_cart_successful(self) -> None:
        """Verify item can be completely removed from cart session."""
        session = self.client.session
        session['cart'] = {
            str(self.product_limited.id): 2,
            str(self.product_secondary.id): 1
        }
        session.save()

        url = reverse('catalog:cart_remove', args=[self.product_limited.id])
        response = self.client.post(url)

        self.assertEqual(response.status_code, 302)
        session_cart = self.client.session.get('cart', {})
        self.assertNotIn(str(self.product_limited.id), session_cart)
        self.assertIn(str(self.product_secondary.id), session_cart)

    def test_invalid_quantity_input_fallback(self) -> None:
        """Invalid inputs (empty, zero, negative, non-numeric) fall back to 1."""
        url = reverse('catalog:add_to_cart', args=[self.product_limited.id])
        invalid_inputs = ['', '0', '-5', 'abc', '   ']

        for invalid in invalid_inputs:
            client = Client()
            client.post(url, {'quantity': invalid})
            session_cart = client.session.get('cart', {})
            self.assertEqual(session_cart[str(self.product_limited.id)], 1)

    def test_quantity_exceeds_max_fallback(self) -> None:
        """Quantity > 99 is rejected – redirects to product detail, cart stays empty."""
        url = reverse('catalog:add_to_cart', args=[self.product_limited.id])
        response = self.client.post(url, {'quantity': '100'})

        session_cart = self.client.session.get('cart', {})
        self.assertNotIn(str(self.product_limited.id), session_cart)
        self.assertRedirects(response, reverse('catalog:product_detail', args=[self.product_limited.slug]))

    def test_add_to_cart_accumulates(self) -> None:
        """Adding same product twice without override accumulates quantity."""
        url = reverse('catalog:add_to_cart', args=[self.product_limited.id])
        self.client.post(url, {'quantity': 2})
        self.client.post(url, {'quantity': 3})

        session_cart = self.client.session.get('cart', {})
        self.assertEqual(session_cart[str(self.product_limited.id)], 5)

    # ===================== CART CONTEXT TESTS =====================
    def test_cart_detail_context(self) -> None:
        """Cart detail view returns full context with items, totals, and correct subtotals."""
        session = self.client.session
        session['cart'] = {
            str(self.product_limited.id): 2,
            str(self.product_secondary.id): 3,
        }
        session.save()

        url = reverse('catalog:cart_detail')
        response = self.client.get(url)

        self.assertEqual(response.status_code, 200)
        context = response.context

        self.assertIn('items', context)
        items = context['items']
        self.assertEqual(len(items), 2)

        item1 = next(i for i in items if i['product'].id == self.product_limited.id)
        self.assertEqual(item1['quantity'], 2)
        self.assertEqual(item1['subtotal_gross'], self.product_limited.price_gross * 2)

        item2 = next(i for i in items if i['product'].id == self.product_secondary.id)
        self.assertEqual(item2['quantity'], 3)
        self.assertEqual(item2['subtotal_gross'], self.product_secondary.price_gross * 3)

        self.assertIn('total_quantity', context)
        self.assertEqual(context['total_quantity'], 5)

        self.assertIn('total_gross', context)
        expected_total_gross = (
            self.product_limited.price_gross * 2 +
            self.product_secondary.price_gross * 3
        )
        self.assertEqual(context['total_gross'], expected_total_gross)

        self.assertIn('total_net', context)
        expected_total_net = (
            self.product_limited.price_net * 2 +
            self.product_secondary.price_net * 3
        )
        self.assertEqual(context['total_net'], expected_total_net)

    def test_cart_detail_empty(self) -> None:
        """Cart detail handles empty cart and returns zero totals with empty items list."""
        session = self.client.session
        session['cart'] = {}
        session.save()

        url = reverse('catalog:cart_detail')
        response = self.client.get(url)

        self.assertEqual(response.status_code, 200)
        context = response.context
        self.assertEqual(context['items'], [])
        self.assertEqual(context['total_quantity'], 0)
        self.assertEqual(context['total_net'], Decimal('0.00'))
        self.assertEqual(context['total_gross'], Decimal('0.00'))

    # ===================== AJAX CART TESTS =====================
    def test_add_to_cart_ajax(self) -> None:
        """AJAX add to cart returns JSON with correct data."""
        url = reverse('catalog:add_to_cart', args=[self.product_limited.id])
        response = self.client.post(
            url,
            {'quantity': 2},
            HTTP_X_REQUESTED_WITH='XMLHttpRequest'
        )

        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertTrue(data['success'])
        self.assertEqual(data['cart_total_quantity'], 2)
        self.assertEqual(data['item_quantity'], 2)
        # No bulk/overlimit flags for normal quantity
        self.assertNotIn('is_bulk', data)
        self.assertNotIn('bulk_warning', data)

    def test_add_to_cart_ajax_over_limit(self) -> None:
        """AJAX add to cart for >99 pcs returns success=False with error message."""
        url = reverse('catalog:add_to_cart', args=[self.product_secondary.id])
        response = self.client.post(
            url,
            {'quantity': 100},
            HTTP_X_REQUESTED_WITH='XMLHttpRequest'
        )

        self.assertEqual(response.status_code, 400)
        data = response.json()
        self.assertFalse(data['success'])
        self.assertIn('error', data)
        self.assertIn('individuální poptávku', data['error'])

    def test_update_cart_ajax(self) -> None:
        """AJAX update quantity (via add_to_cart with override) returns JSON with recalculated totals."""
        session = self.client.session
        session['cart'] = {str(self.product_limited.id): 3}
        session.save()

        url = reverse('catalog:add_to_cart', args=[self.product_limited.id])
        response = self.client.post(
            url,
            {'quantity': 5, 'override': 'on'},
            HTTP_X_REQUESTED_WITH='XMLHttpRequest'
        )

        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertTrue(data['success'])
        self.assertEqual(data['item_quantity'], 5)
        self.assertEqual(data['cart_total_quantity'], 5)

        expected_total_gross = f"{(self.product_limited.price_gross * 5):.2f}"
        self.assertEqual(data['total_gross'], expected_total_gross)

    def test_remove_from_cart_ajax(self) -> None:
        """AJAX remove item returns JSON with updated totals."""
        session = self.client.session
        session['cart'] = {
            str(self.product_limited.id): 2,
            str(self.product_secondary.id): 3,
        }
        session.save()

        url = reverse('catalog:cart_remove', args=[self.product_limited.id])
        response = self.client.post(
            url,
            HTTP_X_REQUESTED_WITH='XMLHttpRequest'
        )

        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertTrue(data['success'])
        self.assertEqual(data['cart_total_quantity'], 3)  # only secondary remains

        expected_total_gross = f"{(self.product_secondary.price_gross * 3):.2f}"
        self.assertEqual(data['total_gross'], expected_total_gross)

    def test_add_to_cart_ajax_out_of_stock(self) -> None:
        """Out-of-stock product returns stock warning in JSON."""
        self.product_limited.stock = 0
        self.product_limited.save()

        url = reverse('catalog:add_to_cart', args=[self.product_limited.id])
        response = self.client.post(
            url,
            {'quantity': 1, 'overstock_confirmed': True},
            HTTP_X_REQUESTED_WITH='XMLHttpRequest'
        )
        data = response.json()
        self.assertIn('stock_warning', data)
        self.assertIsNotNone(data['stock_warning'])
        self.assertIn('není skladem', data['stock_warning'])
