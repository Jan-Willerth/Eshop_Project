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

        # Check redirect and inspect session cart contents
        self.assertEqual(response.status_code, 302)
        session_cart = self.client.session.get('cart', {})
        self.assertIn(str(self.product_limited.id), session_cart)
        self.assertEqual(session_cart[str(self.product_limited.id)], 2)

    def test_add_to_cart_without_stock_limit(self) -> None:
        """Verify ordering more units than physical stock is allowed (no capping)."""
        url = reverse('catalog:add_to_cart', args=[self.product_limited.id])

        # Stock is 5, requested quantity is 15
        self.client.post(url, {'quantity': 15})

        session_cart = self.client.session.get('cart', {})
        self.assertEqual(session_cart[str(self.product_limited.id)], 15)

    def test_update_cart_quantity_override(self) -> None:
        """Verify cart update directly overrides existing quantity instead of adding to it."""
        # Populate initial session cart
        session = self.client.session
        session['cart'] = {str(self.product_limited.id): 3}
        session.save()

        # Submit request with override flag enabled (use 'on' which BooleanField accepts)
        url = reverse('catalog:add_to_cart', args=[self.product_limited.id])
        self.client.post(url, {'quantity': 7, 'override': 'on'})

        session_cart = self.client.session.get('cart', {})
        self.assertEqual(session_cart[str(self.product_limited.id)], 7)

    def test_remove_from_cart_successful(self) -> None:
        """Verify item can be completely removed from cart session."""
        # Prepare multi-item cart in session
        session = self.client.session
        session['cart'] = {
            str(self.product_limited.id): 2,
            str(self.product_secondary.id): 1
        }
        session.save()

        # Remove target product and check remaining items
        url = reverse('catalog:cart_remove', args=[self.product_limited.id])
        response = self.client.post(url)

        self.assertEqual(response.status_code, 302)
        session_cart = self.client.session.get('cart', {})
        self.assertNotIn(str(self.product_limited.id), session_cart)
        self.assertIn(str(self.product_secondary.id), session_cart)

    def test_invalid_quantity_input_fallback(self) -> None:
        """
        Verify invalid inputs (empty, zero, negative, non-numeric) fall back to 1.
        """
        url = reverse('catalog:add_to_cart', args=[self.product_limited.id])
        invalid_inputs = ['', '0', '-5', 'abc', '   ']

        for invalid in invalid_inputs:
            # Reset cart before each sub-test
            self.client.session['cart'] = {}
            self.client.session.save()

            self.client.post(url, {'quantity': invalid})
            session_cart = self.client.session.get('cart', {})
            self.assertEqual(session_cart[str(self.product_limited.id)], 1)

    # ===================== CART CONTEXT TESTS =====================
    def test_cart_detail_context(self) -> None:
        """
        Verify that cart_detail view returns full context with items,
        totals, and correct subtotals.
        """
        # Prepare session cart with two products
        session = self.client.session
        session['cart'] = {
            str(self.product_limited.id): 2,
            str(self.product_secondary.id): 3,
        }
        session.save()

        # Fetch cart detail page
        url = reverse('catalog:cart_detail')
        response = self.client.get(url)

        self.assertEqual(response.status_code, 200)
        context = response.context

        # Check items list
        self.assertIn('items', context)
        items = context['items']
        self.assertEqual(len(items), 2)

        # Verify first item
        item1 = next(i for i in items if i['product'].id == self.product_limited.id)
        self.assertEqual(item1['quantity'], 2)
        self.assertEqual(
            item1['subtotal_gross'],
            self.product_limited.price_gross * 2
        )

        # Verify second item
        item2 = next(i for i in items if i['product'].id == self.product_secondary.id)
        self.assertEqual(item2['quantity'], 3)
        self.assertEqual(
            item2['subtotal_gross'],
            self.product_secondary.price_gross * 3
        )

        # Check totals
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
        """
        Verify that cart_detail view handles empty cart gracefully
        and returns zero totals with empty items list.
        """
        # Ensure session cart is empty
        session = self.client.session
        session['cart'] = {}
        session.save()

        url = reverse('catalog:cart_detail')
        response = self.client.get(url)

        self.assertEqual(response.status_code, 200)
        context = response.context

        # Check items list is empty
        self.assertIn('items', context)
        self.assertEqual(context['items'], [])

        # Check all totals are zero
        self.assertIn('total_quantity', context)
        self.assertEqual(context['total_quantity'], 0)

        self.assertIn('total_net', context)
        self.assertEqual(context['total_net'], Decimal('0.00'))

        self.assertIn('total_gross', context)
        self.assertEqual(context['total_gross'], Decimal('0.00'))

    def test_add_to_cart_accumulates(self) -> None:
        """Verify that adding same product again increases quantity (no override)."""
        # Add first time
        url = reverse('catalog:add_to_cart', args=[self.product_limited.id])
        self.client.post(url, {'quantity': 2})
        # Add second time without override
        self.client.post(url, {'quantity': 3})
        session_cart = self.client.session.get('cart', {})
        self.assertEqual(session_cart[str(self.product_limited.id)], 5)

    def test_quantity_exceeds_max_fallback(self) -> None:
        """Verify quantity > 50 falls back to 1 (form max_value validation)."""
        url = reverse('catalog:add_to_cart', args=[self.product_limited.id])
        self.client.post(url, {'quantity': '55'})

        session_cart = self.client.session.get('cart', {})
        self.assertEqual(session_cart[str(self.product_limited.id)], 1)

    # ===================== AJAX CART TESTS =====================
    def test_add_to_cart_ajax(self) -> None:
        """Test AJAX add to cart returns JSON with correct data."""
        url = reverse('catalog:add_to_cart_ajax', args=[self.product_limited.id])
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

    def test_update_cart_ajax(self) -> None:
        """Test AJAX update quantity returns JSON with recalculated totals."""
        # Prepare cart with one item
        session = self.client.session
        session['cart'] = {str(self.product_limited.id): 3}
        session.save()

        url = reverse('catalog:update_cart_ajax', args=[self.product_limited.id])
        response = self.client.post(
            url,
            {'quantity': 5},
            HTTP_X_REQUESTED_WITH='XMLHttpRequest'
        )

        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertTrue(data['success'])
        self.assertEqual(data['item_quantity'], 5)
        self.assertEqual(data['cart_total_quantity'], 5)

        # Formátováno na 2 desetinná místa
        expected_total_gross = f"{(self.product_limited.price_gross * 5):.2f}"
        self.assertEqual(data['total_gross'], expected_total_gross)

    def test_remove_from_cart_ajax(self) -> None:
        """Test AJAX remove item returns JSON with updated totals."""
        # Prepare cart with two items
        session = self.client.session
        session['cart'] = {
            str(self.product_limited.id): 2,
            str(self.product_secondary.id): 3,
        }
        session.save()

        url = reverse('catalog:remove_from_cart_ajax', args=[self.product_limited.id])
        response = self.client.post(
            url,
            HTTP_X_REQUESTED_WITH='XMLHttpRequest'
        )

        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertTrue(data['success'])
        self.assertEqual(data['cart_total_quantity'], 3)  # only secondary remains

        # Formátováno na 2 desetinná místa
        expected_total_gross = f"{(self.product_secondary.price_gross * 3):.2f}"
        self.assertEqual(data['total_gross'], expected_total_gross)

    def test_add_to_cart_ajax_out_of_stock(self) -> None:
        """Test that out-of-stock product returns stock warning."""
        self.product_limited.stock = 0
        self.product_limited.save()

        url = reverse('catalog:add_to_cart_ajax', args=[self.product_limited.id])
        response = self.client.post(url, {'quantity': 1}, HTTP_X_REQUESTED_WITH='XMLHttpRequest')
        data = response.json()
        self.assertIn('stock_warning', data)
        self.assertIsNotNone(data['stock_warning'])
        self.assertIn('není skladem', data['stock_warning'])
