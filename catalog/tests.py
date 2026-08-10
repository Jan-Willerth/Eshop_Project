import json
from decimal import Decimal

from django.test import TestCase, Client
from django.urls import reverse

from catalog.models import Category, Product, VatRate, ShippingMethod, PaymentMethod


# ===================== CART TESTS =====================
class CartViewsTestCase(TestCase):
    """Test suite for cart views, forms, and session handling."""

    def setUp(self):
        self.client = Client()

        self.vat_standard = VatRate.objects.create(
            label='21%',
            rate=Decimal('21.00'),
            is_active=True
        )

        self.category = Category.objects.create(
            name='Filamenty',
            slug='filamenty',
            is_active=True
        )

        self.product_limited = Product.objects.create(
            name='Spectrum PLA – bílá',
            slug='spectrum-pla-bila',
            price_net=Decimal('450.00'),
            vat_rate=self.vat_standard,
            category=self.category,
            stock=5,
            is_active=True
        )

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
    def test_add_to_cart_successful(self):
        """Adding a valid quantity saves a dict with quantity and overstock_confirmed=False."""
        url = reverse('catalog:add_to_cart', args=[self.product_limited.id])
        response = self.client.post(url, {'quantity': 2})

        self.assertEqual(response.status_code, 302)
        cart = self.client.session.get('cart', {})
        self.assertIn(str(self.product_limited.id), cart)
        self.assertEqual(
            cart[str(self.product_limited.id)],
            {'quantity': 2, 'overstock_confirmed': False}
        )

    def test_add_to_cart_overstock_without_confirmation(self):
        """Adding more than stock without confirmation redirects back and leaves cart unchanged."""
        url = reverse('catalog:add_to_cart', args=[self.product_limited.id])
        response = self.client.post(url, {'quantity': 15})

        self.assertEqual(response.status_code, 302)
        self.assertIn(
            reverse('catalog:product_detail', args=[self.product_limited.slug]),
            response.url
        )
        cart = self.client.session.get('cart', {})
        self.assertNotIn(str(self.product_limited.id), cart)

    def test_add_to_cart_overstock_with_confirmation(self):
        """Overstock with confirmation saves a dict with overstock_confirmed=True."""
        url = reverse('catalog:add_to_cart', args=[self.product_limited.id])
        response = self.client.post(url, {
            'quantity': 15,
            'overstock_confirmed': True
        })

        self.assertEqual(response.status_code, 302)
        cart = self.client.session.get('cart', {})
        self.assertIn(str(self.product_limited.id), cart)
        self.assertEqual(
            cart[str(self.product_limited.id)],
            {'quantity': 15, 'overstock_confirmed': True}
        )

    def test_update_cart_quantity_override(self):
        """Override replaces existing cart entry quantity and resets overstock flag."""
        session = self.client.session
        session['cart'] = {str(self.product_limited.id): {'quantity': 3, 'overstock_confirmed': False}}
        session.save()

        url = reverse('catalog:add_to_cart', args=[self.product_limited.id])
        self.client.post(url, {
            'quantity': 7,
            'override': 'on',
            'overstock_confirmed': True
        })

        cart = self.client.session.get('cart', {})
        self.assertEqual(
            cart[str(self.product_limited.id)],
            {'quantity': 7, 'overstock_confirmed': True}
        )

    def test_remove_from_cart_successful(self):
        """Removing an item deletes only that entry from the cart."""
        session = self.client.session
        session['cart'] = {
            str(self.product_limited.id): {'quantity': 2, 'overstock_confirmed': False},
            str(self.product_secondary.id): {'quantity': 1, 'overstock_confirmed': False},
        }
        session.save()

        url = reverse('catalog:cart_remove', args=[self.product_limited.id])
        response = self.client.post(url)

        self.assertEqual(response.status_code, 302)
        cart = self.client.session.get('cart', {})
        self.assertNotIn(str(self.product_limited.id), cart)
        self.assertIn(str(self.product_secondary.id), cart)

    def test_invalid_quantity_input_fallback(self):
        """Invalid quantity values (empty, zero, negative, non-numeric) default to 1."""
        url = reverse('catalog:add_to_cart', args=[self.product_limited.id])
        invalid_inputs = ['', '0', '-5', 'abc', '   ']

        for invalid in invalid_inputs:
            client = Client()
            client.post(url, {'quantity': invalid})
            cart = client.session.get('cart', {})
            self.assertEqual(
                cart[str(self.product_limited.id)],
                {'quantity': 1, 'overstock_confirmed': False}
            )

    def test_quantity_exceeds_max_fallback(self):
        """Quantity > 99 is rejected and redirects to product detail."""
        url = reverse('catalog:add_to_cart', args=[self.product_limited.id])
        response = self.client.post(url, {'quantity': '100'})

        cart = self.client.session.get('cart', {})
        self.assertNotIn(str(self.product_limited.id), cart)
        self.assertRedirects(
            response,
            reverse('catalog:product_detail', args=[self.product_limited.slug])
        )

    def test_add_to_cart_accumulates(self):
        """Adding the same product twice without override accumulates quantity."""
        url = reverse('catalog:add_to_cart', args=[self.product_limited.id])
        self.client.post(url, {'quantity': 2})
        self.client.post(url, {'quantity': 3})

        cart = self.client.session.get('cart', {})
        self.assertEqual(
            cart[str(self.product_limited.id)],
            {'quantity': 5, 'overstock_confirmed': False}
        )

    # ===================== CART CONTEXT TESTS =====================
    def test_cart_detail_context(self):
        """Cart detail view returns items, totals, and correct subtotals."""
        session = self.client.session
        session['cart'] = {
            str(self.product_limited.id): {'quantity': 2, 'overstock_confirmed': False},
            str(self.product_secondary.id): {'quantity': 3, 'overstock_confirmed': False},
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

        self.assertEqual(context['total_quantity'], 5)

        expected_total_gross = (
            self.product_limited.price_gross * 2 +
            self.product_secondary.price_gross * 3
        )
        self.assertEqual(context['total_gross'], expected_total_gross)

        expected_total_net = (
            self.product_limited.price_net * 2 +
            self.product_secondary.price_net * 3
        )
        self.assertEqual(context['total_net'], expected_total_net)

    def test_cart_detail_empty(self):
        """Empty cart returns zero totals and an empty item list."""
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
    def test_add_to_cart_ajax(self):
        """AJAX add to cart returns JSON with success and totals."""
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
        self.assertNotIn('is_bulk', data)
        self.assertNotIn('bulk_warning', data)

    def test_add_to_cart_ajax_over_limit(self):
        """AJAX request for >99 pcs returns error JSON."""
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

    def test_update_cart_ajax(self):
        """AJAX update (override) returns recalculated JSON totals."""
        session = self.client.session
        session['cart'] = {str(self.product_limited.id): {'quantity': 3, 'overstock_confirmed': False}}
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

    def test_remove_from_cart_ajax(self):
        """AJAX remove returns JSON with updated cart summary."""
        session = self.client.session
        session['cart'] = {
            str(self.product_limited.id): {'quantity': 2, 'overstock_confirmed': False},
            str(self.product_secondary.id): {'quantity': 3, 'overstock_confirmed': False},
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
        self.assertEqual(data['cart_total_quantity'], 3)

        expected_total_gross = f"{(self.product_secondary.price_gross * 3):.2f}"
        self.assertEqual(data['total_gross'], expected_total_gross)

    def test_add_to_cart_ajax_out_of_stock(self):
        """Out-of-stock product triggers a stock warning in JSON."""
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


# ===================== ORDER FORM TESTS =====================
from catalog.forms import OrderForm


class OrderFormTestCase(TestCase):
    """Test suite for the checkout OrderForm (Blok 6)."""

    def setUp(self):
        self.vat_standard = VatRate.objects.create(
            label='21%',
            rate=Decimal('21.00'),
            is_active=True
        )
        self.shipping_method = ShippingMethod.objects.create(
            name='Balík do ruky',
            price_net=Decimal('99.00'),
            vat_rate=self.vat_standard,
            is_active=True
        )
        self.payment_method = PaymentMethod.objects.create(
            name='Platba kartou',
            price_net=Decimal('0.00'),
            vat_rate=self.vat_standard,
            is_active=True
        )
        self.base_data = {
            'customer_email': 'jan@example.com',
            'customer_phone': '+420123456789',
            'shipping_first_name': 'Jan',
            'shipping_last_name': 'Novák',
            'shipping_street': 'Hlavní 1',
            'shipping_city': 'Praha',
            'shipping_zip_code': '11000',
            'shipping_method': self.shipping_method.id,
            'payment_method': self.payment_method.id,
        }

    def test_order_form_valid_data(self):
        """A fully filled-in form with required fields only is valid."""
        form = OrderForm(data=self.base_data)
        self.assertTrue(form.is_valid(), form.errors)

    def test_order_form_billing_different_valid(self):
        """When billing_different is checked, complete billing data is valid."""
        form_data = {
            **self.base_data,
            'billing_different': True,
            'billing_company_name': 'Firma s.r.o.',
            'billing_ico': '12345678',
            'billing_street': 'Firemní 5',
            'billing_city': 'Brno',
            'billing_zip_code': '60200',
        }
        form = OrderForm(data=form_data)
        self.assertTrue(form.is_valid(), form.errors)

    def test_order_form_billing_different_missing_ico(self):
        """When billing_different is checked, missing billing_ico is invalid."""
        form_data = {
            **self.base_data,
            'billing_different': True,
            'billing_company_name': 'Firma s.r.o.',
            'billing_street': 'Firemní 5',
            'billing_city': 'Brno',
            'billing_zip_code': '60200',
        }
        form = OrderForm(data=form_data)
        self.assertFalse(form.is_valid())
        self.assertIn('billing_ico', form.errors)

    def test_order_form_capitalizes_shipping_names(self):
        """Shipping first/last name are capitalized regardless of input casing."""
        form_data = {**self.base_data, 'shipping_first_name': 'jan', 'shipping_last_name': 'novák'}
        form = OrderForm(data=form_data)

        self.assertTrue(form.is_valid(), form.errors)
        self.assertEqual(form.cleaned_data['shipping_first_name'], 'Jan')
        self.assertEqual(form.cleaned_data['shipping_last_name'], 'Novák')

    def test_order_form_billing_ico_invalid_length(self):
        """billing_ico must be exactly 8 digits when billing_different is checked."""
        form_data = {
            **self.base_data,
            'billing_different': True,
            'billing_company_name': 'Firma s.r.o.',
            'billing_ico': '123',
            'billing_street': 'Firemní 5',
            'billing_city': 'Brno',
            'billing_zip_code': '60200',
        }
        form = OrderForm(data=form_data)

        self.assertFalse(form.is_valid())
        self.assertIn('billing_ico', form.errors)

    def test_order_form_billing_ico_valid_length(self):
        """billing_ico with exactly 8 digits passes validation."""
        form_data = {
            **self.base_data,
            'billing_different': True,
            'billing_company_name': 'Firma s.r.o.',
            'billing_ico': '12345678',
            'billing_street': 'Firemní 5',
            'billing_city': 'Brno',
            'billing_zip_code': '60200',
        }
        form = OrderForm(data=form_data)

        self.assertTrue(form.is_valid(), form.errors)


# ===================== ORDER VIEW TESTS =====================
class OrderViewTestCase(TestCase):
    """Test suite for the checkout view (Blok 6)."""

    def setUp(self):
        self.vat_standard = VatRate.objects.create(
            label='21%',
            rate=Decimal('21.00'),
            is_active=True
        )
        self.shipping_method = ShippingMethod.objects.create(
            name='Balík do ruky',
            price_net=Decimal('99.00'),
            vat_rate=self.vat_standard,
            is_active=True
        )
        self.payment_method = PaymentMethod.objects.create(
            name='Platba kartou',
            price_net=Decimal('0.00'),
            vat_rate=self.vat_standard,
            is_active=True
        )
        self.base_data = {
            'customer_email': 'jan@example.com',
            'customer_phone': '+420123456789',
            'shipping_first_name': 'Jan',
            'shipping_last_name': 'Novák',
            'shipping_street': 'Hlavní 1',
            'shipping_city': 'Praha',
            'shipping_zip_code': '11000',
            'shipping_method': self.shipping_method.id,
            'payment_method': self.payment_method.id,
        }
        self.limited_product = Product.objects.create(
            name='Spectrum PLA – bílá',
            slug='spectrum-pla-bila-checkout',
            price_net=Decimal('450.00'),
            vat_rate=self.vat_standard,
            category=Category.objects.create(name='Filamenty', slug='filamenty-checkout', is_active=True),
            stock=5,
            is_active=True
        )

    def test_checkout_get_renders_form(self):
        """GET request renders the checkout page with an OrderForm instance."""
        url = reverse('catalog:checkout')
        response = self.client.get(url)

        self.assertEqual(response.status_code, 200)
        self.assertIsInstance(response.context['form'], OrderForm)

    def test_checkout_post_invalid_data_rerenders_with_errors(self):
        """POST with missing required field re-renders the form with errors, status 200."""
        url = reverse('catalog:checkout')
        invalid_data = {**self.base_data, 'customer_email': ''}
        response = self.client.post(url, invalid_data)

        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.context['form'].is_valid())
        self.assertIn('customer_email', response.context['form'].errors)

    def test_checkout_post_valid_data_redirects(self):
        """POST with valid data redirects away from the checkout page."""
        url = reverse('catalog:checkout')
        response = self.client.post(url, self.base_data)

        self.assertEqual(response.status_code, 302)

    def test_checkout_get_redirects_when_cart_has_unconfirmed_overstock(self):
        """GET checkout redirects to cart with an error when cart has unconfirmed overstock."""
        session = self.client.session
        session['cart'] = {
            str(self.limited_product.id): {'quantity': 10, 'overstock_confirmed': False}
        }
        session.save()

        url = reverse('catalog:checkout')
        response = self.client.get(url)

        self.assertRedirects(response, reverse('catalog:cart_detail'))

    def test_checkout_post_rejected_when_cart_has_unconfirmed_overstock(self):
        """POST checkout does not process the order when cart has unconfirmed overstock."""
        session = self.client.session
        session['cart'] = {
            str(self.limited_product.id): {'quantity': 10, 'overstock_confirmed': False}
        }
        session.save()

        url = reverse('catalog:checkout')
        response = self.client.post(url, self.base_data)

        self.assertRedirects(response, reverse('catalog:cart_detail'))

    def test_checkout_post_valid_saves_pending_order_and_redirects_to_summary(self):
        """Valid POST saves form data to session['pending_order'] and redirects to summary."""
        url = reverse('catalog:checkout')
        response = self.client.post(url, self.base_data)

        self.assertRedirects(response, reverse('catalog:checkout_summary'))

        pending_order = self.client.session.get('pending_order')
        self.assertIsNotNone(pending_order)
        self.assertEqual(pending_order['customer_email'], 'jan@example.com')
        self.assertEqual(pending_order['shipping_method_id'], self.shipping_method.id)
        self.assertEqual(pending_order['payment_method_id'], self.payment_method.id)

    def test_checkout_summary_get_shows_items_and_totals(self):
        """GET summary page shows cart items, shipping/payment price, and grand total."""
        session = self.client.session
        session['cart'] = {
            str(self.limited_product.id): {'quantity': 2, 'overstock_confirmed': False}
        }
        session['pending_order'] = {
            'customer_email': 'jan@example.com',
            'customer_phone': '+420123456789',
            'shipping_first_name': 'Jan',
            'shipping_last_name': 'Novák',
            'shipping_street': 'Hlavní 1',
            'shipping_city': 'Praha',
            'shipping_zip_code': '11000',
            'shipping_method_id': self.shipping_method.id,
            'payment_method_id': self.payment_method.id,
            'billing_different': False,
            'billing_first_name': '',
            'billing_last_name': '',
            'billing_company_name': '',
            'billing_ico': '',
            'billing_dic': '',
            'billing_street': '',
            'billing_city': '',
            'billing_zip_code': '',
        }
        session.save()

        url = reverse('catalog:checkout_summary')
        response = self.client.get(url)

        self.assertEqual(response.status_code, 200)
        context = response.context

        self.assertEqual(len(context['items']), 1)
        self.assertEqual(context['items'][0]['quantity'], 2)

        expected_products_gross = self.limited_product.price_gross * 2
        expected_grand_total = expected_products_gross + self.shipping_method.price_gross + self.payment_method.price_gross

        self.assertEqual(context['products_total_gross'], expected_products_gross)
        self.assertEqual(context['shipping'].price_gross, self.shipping_method.price_gross)
        self.assertEqual(context['payment'].price_gross, self.payment_method.price_gross)
        self.assertEqual(context['grand_total_gross'], expected_grand_total)

    def test_checkout_summary_get_redirects_without_pending_order(self):
        """GET summary page redirects to checkout form if no pending_order in session."""
        url = reverse('catalog:checkout_summary')
        response = self.client.get(url)

        self.assertRedirects(response, reverse('catalog:checkout'))


# ===================== SHIPPING & PAYMENT MODEL TESTS =====================
class ShippingPaymentModelTestCase(TestCase):
    """Test suite for gross price calculation on ShippingMethod and PaymentMethod."""

    def setUp(self):
        self.vat_standard = VatRate.objects.create(
            label='21%',
            rate=Decimal('21.00'),
            is_active=True
        )

    def test_shipping_method_price_gross(self):
        """ShippingMethod.price_gross includes VAT on top of price_net."""
        shipping = ShippingMethod.objects.create(
            name='Zásilkovna',
            price_net=Decimal('89.00'),
            vat_rate=self.vat_standard,
            is_active=True
        )
        self.assertEqual(shipping.price_gross, Decimal('107.69'))

    def test_payment_method_price_gross(self):
        """PaymentMethod.price_gross includes VAT on top of price_net."""
        payment = PaymentMethod.objects.create(
            name='Dobírka',
            price_net=Decimal('40.00'),
            vat_rate=self.vat_standard,
            is_active=True
        )
        self.assertEqual(payment.price_gross, Decimal('48.40'))
