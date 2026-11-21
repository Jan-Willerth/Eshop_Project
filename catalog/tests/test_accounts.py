from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse

from catalog.forms import RegistrationForm
from catalog.models import Profile


# ===================== REGISTRATION FORM TESTS =====================
class RegistrationFormTestCase(TestCase):
    """Test suite for the RegistrationForm (Blok 8)."""

    def setUp(self):
        self.valid_data = {
            'email': 'novy@example.com',
            'first_name': 'Jan',
            'last_name': 'Novák',
            'phone': '+420123456789',
            'street': 'Hlavní 1',
            'city': 'Praha',
            'zip_code': '11000',
            'password1': 'SilneHeslo123',
            'password2': 'SilneHeslo123',
        }

    def test_registration_form_valid_data(self):
        """Valid data produces a valid form."""
        form = RegistrationForm(data=self.valid_data)
        self.assertTrue(form.is_valid(), form.errors)

    def test_registration_form_duplicate_email(self):
        """Registering with an already-used email is invalid."""
        User.objects.create_user(
            username='existujici@example.com',
            email='existujici@example.com',
            password='Heslo123456',
        )

        form = RegistrationForm(
            data={**self.valid_data, 'email': 'existujici@example.com'}
        )
        self.assertFalse(form.is_valid())
        self.assertIn('email', form.errors)

    def test_registration_form_saves_user_and_profile(self):
        """Saving the form creates a User (email as username) and a linked
        Profile.
        """
        form = RegistrationForm(data=self.valid_data)
        self.assertTrue(form.is_valid(), form.errors)

        user = form.save()

        self.assertEqual(user.username, 'novy@example.com')
        self.assertEqual(user.email, 'novy@example.com')
        self.assertEqual(user.first_name, 'Jan')
        self.assertEqual(user.last_name, 'Novák')

        self.assertEqual(user.profile.phone, '+420123456789')
        self.assertEqual(user.profile.street, 'Hlavní 1')
        self.assertEqual(user.profile.city, 'Praha')
        self.assertEqual(user.profile.zip_code, '11000')

    def test_registration_with_company_invoice_saves_billing_profile(self):
        """B2B registration stores optional company data linked to the user
        profile.
        """
        form = RegistrationForm(data={
            **self.valid_data,
            'billing_different': True,
            'billing_first_name': 'Jan',
            'billing_last_name': 'Novák',
            'billing_company_name': 'Example s.r.o.',
            'billing_ico': '12345678',
            'billing_dic': 'CZ12345678',
            'billing_street': 'Fakturační 2',
            'billing_city': 'Brno',
            'billing_zip_code': '60200',
        })
        self.assertTrue(form.is_valid(), form.errors)


# ===================== PROFILE UPDATE TESTS =====================
class ProfileUpdateViewTestCase(TestCase):
    """Test suite for customer profile updates."""

    def setUp(self):
        self.user = User.objects.create_user(
            username='profil@example.com',
            email='profil@example.com',
            password='SilneHeslo123',
        )
        Profile.objects.create(
            user=self.user,
            phone='732123456',
            street='Hlavní 1',
            city='Praha',
            zip_code='11000',
        )

    def test_profile_update_creates_company_billing_profile(self):
        self.client.force_login(self.user)
        response = self.client.post(reverse('catalog:profile_update'), {
            'email': self.user.email,
            'first_name': 'Jan',
            'last_name': 'Novák',
            'phone': '732123456',
            'street': 'Hlavní 1',
            'city': 'Praha',
            'zip_code': '11000',
            'billing_different': 'on',
            'billing_first_name': 'Jan',
            'billing_last_name': 'Novák',
            'billing_company_name': 'Example s.r.o.',
            'billing_ico': '12345678',
            'billing_dic': 'CZ12345678',
            'billing_street': 'Fakturační 2',
            'billing_city': 'Brno',
            'billing_zip_code': '60200',
        })

        self.assertRedirects(response, reverse('catalog:profile_update'))
        self.assertEqual(
            self.user.profile.company_billing.company_name,
            'Example s.r.o.',
        )
