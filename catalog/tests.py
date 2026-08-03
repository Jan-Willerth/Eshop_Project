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

        # Submit request with override flag enabled
        url = reverse('catalog:add_to_cart', args=[self.product_limited.id])
        self.client.post(url, {'quantity': 7, 'override': 'True'})

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
        """Verify zero, negative, or invalid input falls back safely to default (1)."""
        url = reverse('catalog:add_to_cart', args=[self.product_limited.id])
        self.client.post(url, {'quantity': '-5'})

        session_cart = self.client.session.get('cart', {})
        self.assertEqual(session_cart[str(self.product_limited.id)], 1)
