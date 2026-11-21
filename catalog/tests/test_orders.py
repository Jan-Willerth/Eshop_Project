from decimal import Decimal

from django.contrib.auth.models import User
from django.core import mail
from django.test import TestCase
from django.urls import reverse

from catalog.forms import OrderForm
from catalog.models import (
    Category,
    Order,
    PaymentMethod,
    Product,
    ShippingMethod,
    OrderStatus,
    VatRate,
)


# ===================== ORDER FORM TESTS =====================
class OrderFormTestCase(TestCase):
    """Test suite for the checkout OrderForm (Blok 6)."""

    def setUp(self):
        self.vat_standard = VatRate.objects.create(
            label='21%',
            rate=Decimal('21.00'),
            is_active=True,
        )
        self.shipping_method = ShippingMethod.objects.create(
            name='Balík do ruky',
            price_net=Decimal('99.00'),
            vat_rate=self.vat_standard,
            is_active=True,
        )
        self.payment_method = PaymentMethod.objects.create(
            name='Platba kartou',
            price_net=Decimal('0.00'),
            vat_rate=self.vat_standard,
            is_active=True,
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
        """Shipping first/last name are capitalized regardless of input
        casing.
        """
        form_data = {
            **self.base_data,
            'shipping_first_name': 'jan',
            'shipping_last_name': 'novák',
        }
        form = OrderForm(data=form_data)

        self.assertTrue(form.is_valid(), form.errors)
        self.assertEqual(form.cleaned_data['shipping_first_name'], 'Jan')
        self.assertEqual(form.cleaned_data['shipping_last_name'], 'Novák')

    def test_order_form_billing_ico_invalid_length(self):
        """billing_ico must be exactly 8 digits when billing_different is
        checked.
        """
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

    def test_anonymous_order_above_limit_requires_advance_payment(self):
        """Anonymous order over 1000 Kč with cash-on-delivery is invalid."""
        cash_on_delivery = PaymentMethod.objects.create(
            name='Dobírka',
            price_net=Decimal('0.00'),
            vat_rate=self.vat_standard,
            is_active=True,
        )
        form = OrderForm(
            data={**self.base_data, 'payment_method': cash_on_delivery.id},
            products_total_gross=Decimal('1001.00'),
        )

        self.assertFalse(form.is_valid())
        self.assertIn('payment_method', form.errors)

    def test_registered_order_above_limit_requires_advance_payment(self):
        """Registered-user order over 5000 Kč with cash-on-delivery is
        invalid.
        """
        cash_on_delivery = PaymentMethod.objects.create(
            name='Dobírka',
            price_net=Decimal('0.00'),
            vat_rate=self.vat_standard,
            is_active=True,
        )
        form = OrderForm(
            data={**self.base_data, 'payment_method': cash_on_delivery.id},
            products_total_gross=Decimal('5001.00'),
            is_registered=True,
        )

        self.assertFalse(form.is_valid())
        self.assertIn('payment_method', form.errors)



# ===================== ORDER VIEW TESTS =====================
class OrderViewTestCase(TestCase):
    """Test suite for the checkout view (Blok 6)."""

    def setUp(self):
        self.vat_standard = VatRate.objects.create(
            label='21%',
            rate=Decimal('21.00'),
            is_active=True,
        )
        self.shipping_method = ShippingMethod.objects.create(
            name='Balík do ruky',
            price_net=Decimal('99.00'),
            vat_rate=self.vat_standard,
            is_active=True,
        )
        self.payment_method = PaymentMethod.objects.create(
            name='Platba kartou',
            price_net=Decimal('0.00'),
            vat_rate=self.vat_standard,
            is_active=True,
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
            category=Category.objects.create(
                name='Filamenty',
                slug='filamenty-checkout',
                is_active=True,
            ),
            stock=5,
            is_active=True,
        )
        self.order_status = OrderStatus.objects.create(code='new', name='Nová')

        self.test_user = User.objects.create_user(
            username='zakaznik@example.com',
            email='zakaznik@example.com',
            password='SilneHeslo123',
        )

    def test_checkout_get_renders_form(self):
        """GET request renders the checkout page with an OrderForm instance."""
        url = reverse('catalog:checkout')
        response = self.client.get(url)

        self.assertEqual(response.status_code, 200)
        self.assertIsInstance(response.context['form'], OrderForm)

    def test_checkout_post_invalid_data_rerenders_with_errors(self):
        """POST with missing required field re-renders the form with errors,
        status 200.
        """
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
        """GET checkout redirects to cart with an error when cart has
        unconfirmed overstock.
        """
        session = self.client.session
        session['cart'] = {
            str(self.limited_product.id): {
                'quantity': 10,
                'overstock_confirmed': False,
            },
        }
        session.save()

        url = reverse('catalog:checkout')
        response = self.client.get(url)

        self.assertRedirects(response, reverse('catalog:cart_detail'))

    def test_checkout_post_rejected_when_cart_has_unconfirmed_overstock(self):
        """POST checkout does not process the order when cart has unconfirmed
        overstock.
        """
        session = self.client.session
        session['cart'] = {
            str(self.limited_product.id): {
                'quantity': 10,
                'overstock_confirmed': False,
            },
        }
        session.save()

        url = reverse('catalog:checkout')
        response = self.client.post(url, self.base_data)

        self.assertRedirects(response, reverse('catalog:cart_detail'))

    def test_checkout_post_valid_saves_pending_order_and_redirects_to_summary(self):
        """Valid POST saves form data to session['pending_order'] and redirects
        to summary.
        """
        url = reverse('catalog:checkout')
        response = self.client.post(url, self.base_data)

        self.assertRedirects(response, reverse('catalog:checkout_summary'))

        pending_order = self.client.session.get('pending_order')
        self.assertIsNotNone(pending_order)
        self.assertEqual(pending_order['customer_email'], 'jan@example.com')
        self.assertEqual(pending_order['shipping_method_id'], self.shipping_method.id)
        self.assertEqual(pending_order['payment_method_id'], self.payment_method.id)

    def test_checkout_summary_get_shows_items_and_totals(self):
        """GET summary page shows item totals and the net grand total."""
        session = self.client.session
        session['cart'] = {
            str(self.limited_product.id): {
                'quantity': 2,
                'overstock_confirmed': False,
            },
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
        expected_products_net = self.limited_product.price_net * 2
        expected_grand_total_net = (
            expected_products_net
            + self.shipping_method.price_net
            + self.payment_method.price_net
        )
        expected_grand_total = (
            expected_products_gross
            + self.shipping_method.price_gross
            + self.payment_method.price_gross
        )

        self.assertEqual(context['products_total_gross'], expected_products_gross)
        self.assertEqual(context['shipping'].price_gross, self.shipping_method.price_gross)
        self.assertEqual(context['payment'].price_gross, self.payment_method.price_gross)
        self.assertEqual(context['grand_total_net'], expected_grand_total_net)
        self.assertEqual(context['grand_total_gross'], expected_grand_total)

    def test_checkout_summary_post_creates_order_and_clears_session(self):
        """POST creates an Order with items and clears the session."""
        session = self.client.session
        session['cart'] = {
            str(self.limited_product.id): {
                'quantity': 2,
                'overstock_confirmed': False,
            },
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
        response = self.client.post(url)

        order = Order.objects.first()
        self.assertRedirects(
            response,
            reverse('catalog:order_success', kwargs={'order_id': order.id}),
        )

        self.assertEqual(Order.objects.count(), 1)
        order = Order.objects.first()

        self.assertEqual(order.items.count(), 1)

        expected_total = (
            self.limited_product.price_gross * 2
            + self.shipping_method.price_gross
            + self.payment_method.price_gross
        )
        self.assertEqual(order.total_price_gross, expected_total)

        self.limited_product.refresh_from_db()
        self.assertEqual(self.limited_product.stock, 3)

        self.assertNotIn('cart', self.client.session)
        self.assertNotIn('pending_order', self.client.session)

    def test_checkout_summary_post_sends_confirmation_email(self):
        """POST creates an order and sends a confirmation email."""
        session = self.client.session
        session['cart'] = {
            str(self.limited_product.id): {
                'quantity': 2,
                'overstock_confirmed': False,
            },
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
        self.client.post(url)

        self.assertEqual(len(mail.outbox), 1)
        email = mail.outbox[0]
        order = Order.objects.first()
        self.assertEqual(email.subject, f'Potvrzení objednávky č. {order.id}')
        self.assertIn('jan@example.com', email.to)
        self.assertIn('Děkujeme za Vaši objednávku', email.body)

    def test_checkout_summary_post_sends_pdf_for_business_order(self):
        """POST sends a PDF invoice attachment when billing_different is True."""
        session = self.client.session
        session['cart'] = {
            str(self.limited_product.id): {
                'quantity': 2,
                'overstock_confirmed': False,
            },
        }
        session['pending_order'] = {
            'customer_email': 'firma@example.com',
            'customer_phone': '+420987654321',
            'shipping_first_name': 'Petr',
            'shipping_last_name': 'Svoboda',
            'shipping_street': 'Obchodní 10',
            'shipping_city': 'Brno',
            'shipping_zip_code': '60200',
            'shipping_method_id': self.shipping_method.id,
            'payment_method_id': self.payment_method.id,
            'billing_different': True,
            'billing_first_name': 'Petr',
            'billing_last_name': 'Svoboda',
            'billing_company_name': 'Firma s.r.o.',
            'billing_ico': '12345678',
            'billing_dic': 'CZ12345678',
            'billing_street': 'Obchodní 10',
            'billing_city': 'Brno',
            'billing_zip_code': '60200',
        }
        session.save()

        url = reverse('catalog:checkout_summary')
        self.client.post(url)

        self.assertEqual(len(mail.outbox), 1)
        email = mail.outbox[0]

        self.assertEqual(len(email.attachments), 1)
        filename, content, mimetype = email.attachments[0]
        self.assertEqual(mimetype, 'application/pdf')
        self.assertTrue(filename.startswith('danovy_doklad_'))

    def test_checkout_summary_post_sends_pdf_for_consumer_order(self):
        """POST sends a simplified tax document PDF attachment for a B2C order
        too.
        """
        session = self.client.session
        session['cart'] = {
            str(self.limited_product.id): {
                'quantity': 2,
                'overstock_confirmed': False,
            },
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
        self.client.post(url)

        self.assertEqual(len(mail.outbox), 1)
        email = mail.outbox[0]

        self.assertEqual(len(email.attachments), 1)
        filename, content, mimetype = email.attachments[0]
        self.assertEqual(mimetype, 'application/pdf')
        self.assertTrue(filename.startswith('zjednoduseny_danovy_doklad_'))

    def test_checkout_summary_get_redirects_without_pending_order(self):
        """GET summary page redirects to checkout form if no pending_order in
        session.
        """
        url = reverse('catalog:checkout_summary')
        response = self.client.get(url)

        self.assertRedirects(response, reverse('catalog:checkout'))

    def test_checkout_summary_post_associates_order_with_logged_in_user(self):
        """POST while logged in sets order.user to the current user."""
        self.client.login(username='zakaznik@example.com', password='SilneHeslo123')

        session = self.client.session
        session['cart'] = {
            str(self.limited_product.id): {
                'quantity': 1,
                'overstock_confirmed': False,
            },
        }
        session['pending_order'] = {
            'customer_email': 'zakaznik@example.com',
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
        self.client.post(url)

        order = Order.objects.first()
        self.assertEqual(order.user, self.test_user)

    def test_checkout_summary_post_anonymous_order_has_no_user(self):
        """POST while anonymous leaves order.user as None."""
        session = self.client.session
        session['cart'] = {
            str(self.limited_product.id): {
                'quantity': 1,
                'overstock_confirmed': False,
            },
        }
        session['pending_order'] = {
            'customer_email': 'anonym@example.com',
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
        self.client.post(url)

        order = Order.objects.first()
        self.assertIsNone(order.user)


# ===================== SHIPPING & PAYMENT MODEL TESTS =====================
class ShippingPaymentModelTestCase(TestCase):
    """Test suite for gross price calculation on ShippingMethod and
    PaymentMethod.
    """

    def setUp(self):
        self.vat_standard = VatRate.objects.create(
            label='21%',
            rate=Decimal('21.00'),
            is_active=True,
        )

    def test_shipping_method_price_gross(self):
        """ShippingMethod.price_gross includes VAT on top of price_net."""
        shipping = ShippingMethod.objects.create(
            name='Zásilkovna',
            price_net=Decimal('89.00'),
            vat_rate=self.vat_standard,
            is_active=True,
        )
        self.assertEqual(shipping.price_gross, Decimal('107.69'))

    def test_payment_method_price_gross(self):
        """PaymentMethod.price_gross includes VAT on top of price_net."""
        payment = PaymentMethod.objects.create(
            name='Dobírka',
            price_net=Decimal('40.00'),
            vat_rate=self.vat_standard,
            is_active=True,
        )
        self.assertEqual(payment.price_gross, Decimal('48.40'))


# ===================== ORDER HISTORY TESTS =====================
class OrderHistoryTestCase(TestCase):
    """Test suite for the 'Moje objednávky' order-history page (Blok 8)."""

    def setUp(self):
        self.vat_standard = VatRate.objects.create(
            label='21%',
            rate=Decimal('21.00'),
            is_active=True,
        )
        self.shipping_method = ShippingMethod.objects.create(
            name='Balík do ruky',
            price_net=Decimal('99.00'),
            vat_rate=self.vat_standard,
            is_active=True,
        )
        self.payment_method = PaymentMethod.objects.create(
            name='Platba kartou',
            price_net=Decimal('0.00'),
            vat_rate=self.vat_standard,
            is_active=True,
        )
        self.order_status = OrderStatus.objects.create(code='new', name='Nová')

        self.user_a = User.objects.create_user(
            username='alice@example.com',
            email='alice@example.com',
            password='SilneHeslo123',
        )
        self.user_b = User.objects.create_user(
            username='bob@example.com',
            email='bob@example.com',
            password='SilneHeslo123',
        )

        self.order_a = self._create_order(self.user_a, 'alice@example.com')
        self.order_b = self._create_order(self.user_b, 'bob@example.com')

    def _create_order(self, user, email):
        return Order.objects.create(
            user=user,
            status=self.order_status,
            shipping_method=self.shipping_method,
            payment_method=self.payment_method,
            shipping_price_net=self.shipping_method.price_net,
            shipping_vat_rate=self.shipping_method.vat_rate.rate,
            payment_price_net=self.payment_method.price_net,
            payment_price_gross=self.payment_method.price_gross,
            payment_vat_rate=self.payment_method.vat_rate.rate,
            total_price_net=Decimal('500.00'),
            total_price_gross=Decimal('605.00'),
            customer_email=email,
            customer_phone='+420123456789',
            shipping_first_name='Jan',
            shipping_last_name='Novák',
            shipping_street='Hlavní 1',
            shipping_city='Praha',
            shipping_zip_code='11000',
        )

    def test_order_history_requires_login(self):
        """Anonymous user is redirected to the login page."""
        url = reverse('catalog:order_history')
        response = self.client.get(url)

        self.assertEqual(response.status_code, 302)
        self.assertIn(reverse('catalog:login'), response.url)

    def test_order_history_shows_only_own_orders(self):
        """Logged-in user sees only their own orders, not other users' orders."""
        self.client.login(username='alice@example.com', password='SilneHeslo123')

        url = reverse('catalog:order_history')
        response = self.client.get(url)

        self.assertEqual(response.status_code, 200)
        orders = response.context['orders']
        self.assertEqual(list(orders), [self.order_a])
        self.assertNotIn(self.order_b, orders)
