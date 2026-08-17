import re
from decimal import Decimal

from django import forms
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth.models import User

from .models import (
    CompanyBillingProfile,
    PaymentMethod,
    Profile,
    QuoteRequest,
    ShippingMethod,
)


# ===================== MIXINS =====================
class PhoneValidationMixin:
    """Mixin to provide centralized Czech phone number validation and client-side attributes."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field_name in ('phone', 'customer_phone'):
            if field_name in self.fields:
                self.fields[field_name].widget.attrs.update({
                    'inputmode': 'tel',
                    'pattern': r'(\d{3}\s*\d{3}\s*\d{3}|\+420\s*\d{3}\s*\d{3}\s*\d{3})',
                    'maxlength': '16',
                    'title': 'Zadejte platné telefonní číslo (9 číslic nebo +420 a 9 číslic).',
                })

    def validate_phone_value(self, phone_value: str) -> str:
        """Validate that the phone number contains a valid format of digits/spaces/plus."""
        if not phone_value:
            return phone_value

        phone_clean = phone_value.replace(' ', '')
        if not re.fullmatch(r'(\d{9}|\+420\d{9})', phone_clean):
            raise forms.ValidationError(
                'Zadejte platné telefonní číslo (9 číslic nebo +420 a 9 číslic).'
            )
        return phone_value


class ZipValidationMixin:
    """Mixin to provide centralized Czech ZIP code validation and client-side attributes."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field_name in ('zip_code', 'billing_zip_code', 'delivery_zip_code', 'customer_zip_code'):
            if field_name in self.fields:
                self.fields[field_name].widget.attrs.update({
                    'inputmode': 'numeric',
                    'pattern': r'\d{3}\s*\d{2}',
                    'maxlength': '6',
                    'title': 'Zadejte platné PSČ (5 číslic, např. 736 01).',
                })

    def validate_zip_value(self, zip_value: str) -> str:
        """Validate that the ZIP code contains exactly 5 digits after removing spaces."""
        if not zip_value:
            return zip_value

        zip_clean = zip_value.replace(' ', '')
        if not re.fullmatch(r'\d{5}', zip_clean):
            raise forms.ValidationError('Zadejte platné PSČ (přesně 5 číslic).')
        return zip_clean


class CompanyIdValidationMixin:
    """Mixin for validating Czech IČO and DIČ including client-side attributes."""

    ICO_FIELDS = ('ico', 'billing_ico')
    DIC_FIELDS = ('dic', 'billing_dic')

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        for field_name in self.ICO_FIELDS:
            if field_name in self.fields:
                self.fields[field_name].widget.attrs.update({
                    'inputmode': 'numeric',
                    'pattern': r'\d{8}',
                    'maxlength': '8',
                    'title': 'IČO musí obsahovat přesně 8 číslic.',
                })

        for field_name in self.DIC_FIELDS:
            if field_name in self.fields:
                self.fields[field_name].widget.attrs.update({
                    'inputmode': 'text',
                    'pattern': r'CZ\d{8}',
                    'maxlength': '10',
                    'title': 'DIČ musí být ve formátu CZ + 8 číslic.',
                })

    def validate_ico_value(self, ico_value: str) -> str:
        """Validate that the value is a valid Czech IČO (8 digits)."""
        if not ico_value:
            return ico_value

        ico_clean = ico_value.replace(' ', '')
        if not re.fullmatch(r'\d{8}', ico_clean):
            raise forms.ValidationError('IČO musí obsahovat přesně 8 číslic.')
        return ico_clean

    def validate_dic_value(self, dic_value: str) -> str:
        """Validate that the value is a valid Czech DIČ (CZ + 8 digits)."""
        if not dic_value:
            return dic_value

        dic_clean = dic_value.replace(' ', '').upper()
        if not re.fullmatch(r'CZ\d{8}', dic_clean):
            raise forms.ValidationError('DIČ musí být ve formátu CZ + 8 číslic.')
        return dic_clean


# ===================== CHOICE FIELDS =====================
class ShippingMethodChoiceField(forms.ModelChoiceField):
    """ModelChoiceField that displays the gross price alongside the shipping method name."""

    def label_from_instance(self, obj):
        return f"{obj.name} — {obj.price_gross:.2f} Kč"


class PaymentMethodChoiceField(forms.ModelChoiceField):
    """ModelChoiceField that displays the gross price alongside the payment method name."""

    def label_from_instance(self, obj):
        return f"{obj.name} — {obj.price_gross:.2f} Kč"


# ===================== CART FORMS =====================
class CartAddProductForm(forms.Form):
    """Validate product quantity and enforce overstock confirmation when needed."""

    quantity = forms.CharField(
        max_length=3,
        required=False,
        initial='1',
        widget=forms.TextInput(attrs={
            'class': 'form-control text-center',
            'min': '1',
            'max': '99',
            'inputmode': 'numeric',
        }),
        error_messages={
            'required': 'Zadejte množství.',
        }
    )

    override = forms.BooleanField(
        required=False,
        initial=False,
        widget=forms.HiddenInput
    )

    overstock_confirmed = forms.BooleanField(
        required=False,
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'})
    )

    def __init__(self, *args, product_stock: int = 0, **kwargs):
        super().__init__(*args, **kwargs)
        self.product_stock = product_stock

    def clean_quantity(self) -> int:
        """Parse quantity from string input, defaulting to 1 for any invalid value."""
        raw = self.cleaned_data.get('quantity', '').strip()
        try:
            qty = int(raw)
        except (ValueError, TypeError):
            return 1

        if qty < 1:
            return 1
        if qty > 99:
            raise forms.ValidationError(
                'Pro objednávky nad 99 ks prosím použijte formulář pro individuální poptávku.',
                code='max_value'
            )
        return qty

    def clean(self):
        """Require overstock confirmation when quantity exceeds available stock."""
        cleaned_data = super().clean()
        quantity = cleaned_data.get('quantity') or 0
        confirmed = cleaned_data.get('overstock_confirmed')

        if quantity > self.product_stock and not confirmed:
            self.add_error(
                'overstock_confirmed',
                f'Poptáváte více kusů, než máme skladem ({self.product_stock} ks). '
                f'Potvrďte prosím souhlas s delší dodací lhůtou.'
            )
        return cleaned_data


# ===================== QUOTE REQUEST FORMS =====================
class QuoteRequestForm(PhoneValidationMixin, forms.ModelForm):
    """Form for submitting an individual quote request for bulk orders."""

    class Meta:
        model = QuoteRequest
        fields = [
            'first_name', 'last_name', 'email', 'phone',
            'product', 'quantity',
            'message', 'agreed_to_terms',
        ]
        widgets = {
            'product': forms.HiddenInput(),
            'quantity': forms.HiddenInput(),
            'message': forms.Textarea(attrs={'rows': 4, 'class': 'form-control'}),
            'first_name': forms.TextInput(attrs={'class': 'form-control'}),
            'last_name': forms.TextInput(attrs={'class': 'form-control'}),
            'email': forms.EmailInput(attrs={'class': 'form-control'}),
        }
        labels = {
            'agreed_to_terms': (
                'Souhlasím s tím, že se na tuto objednávku nevztahuje 14denní lhůta '
                'pro odstoupení od smlouvy, protože se jedná o individuálně sjednanou zakázku.'
            ),
        }

    def clean_quantity(self) -> int:
        """Ensure a valid positive quantity is provided."""
        qty = self.cleaned_data.get('quantity')
        if qty is None or qty < 1:
            raise forms.ValidationError("Neplatné množství.")
        return qty

    def clean_phone(self) -> str:
        return self.validate_phone_value(self.cleaned_data.get('phone'))


# ===================== ORDER FORM =====================
class OrderForm(PhoneValidationMixin, ZipValidationMixin, CompanyIdValidationMixin, forms.Form):
    """Validate checkout, delivery-address choice, and payment limits."""

    customer_email = forms.EmailField(label='E-mail')
    customer_phone = forms.CharField(
        max_length=50,
        required=True,
        label='Telefon',
    )
    shipping_first_name = forms.CharField(max_length=100, required=False, label='Jméno')
    shipping_last_name = forms.CharField(max_length=100, required=False, label='Příjmení')
    shipping_street = forms.CharField(
        max_length=255,
        required=False,
        label='Ulice a číslo popisné',
    )
    shipping_city = forms.CharField(max_length=100, required=False, label='Město')
    shipping_zip_code = forms.CharField(max_length=20, required=False, label='PSČ')
    shipping_method = ShippingMethodChoiceField(
        queryset=ShippingMethod.objects.filter(is_active=True),
        label='Způsob dopravy',
    )
    payment_method = PaymentMethodChoiceField(
        queryset=PaymentMethod.objects.filter(is_active=True),
        label='Způsob platby',
    )

    billing_different = forms.BooleanField(required=False, label='Chci fakturu na firmu')
    billing_first_name = forms.CharField(max_length=100, required=False, label='Jméno (kontaktní osoba)')
    billing_last_name = forms.CharField(max_length=100, required=False, label='Příjmení (kontaktní osoba)')
    billing_company_name = forms.CharField(max_length=150, required=False, label='Název firmy')
    billing_ico = forms.CharField(max_length=20, required=False, label='IČO')
    billing_dic = forms.CharField(max_length=20, required=False, label='DIČ')
    billing_street = forms.CharField(
        max_length=255,
        required=False,
        label='Ulice a číslo popisné (fakturační)',
    )
    billing_city = forms.CharField(max_length=100, required=False, label='Město (fakturační)')
    billing_zip_code = forms.CharField(max_length=20, required=False, label='PSČ (fakturační)')
    billing_address_is_delivery = forms.BooleanField(
        required=False,
        label='Fakturační adresa je stejná jako doručovací',
    )
    delivery_different = forms.BooleanField(required=False, label='Jiná dodací adresa')
    delivery_street = forms.CharField(
        max_length=255,
        required=False,
        label='Ulice a číslo popisné (dodací)',
    )
    delivery_city = forms.CharField(max_length=100, required=False, label='Město (dodací)')
    delivery_zip_code = forms.CharField(max_length=20, required=False, label='PSČ (dodací)')

    def __init__(
        self,
        *args,
        products_total_gross=Decimal('0.00'),
        is_registered=False,
        **kwargs,
    ):
        super().__init__(*args, **kwargs)
        self.products_total_gross = products_total_gross
        self.is_registered = is_registered

    def clean_customer_phone(self) -> str:
        return self.validate_phone_value(self.cleaned_data.get('customer_phone'))

    def clean_shipping_first_name(self) -> str:
        return self.cleaned_data.get('shipping_first_name', '').strip().capitalize()

    def clean_shipping_last_name(self) -> str:
        return self.cleaned_data.get('shipping_last_name', '').strip().capitalize()

    def clean_shipping_zip_code(self) -> str:
        return self.validate_zip_value(self.cleaned_data.get('shipping_zip_code'))

    def clean_billing_zip_code(self) -> str:
        return self.validate_zip_value(self.cleaned_data.get('billing_zip_code'))

    def clean_delivery_zip_code(self) -> str:
        return self.validate_zip_value(self.cleaned_data.get('delivery_zip_code'))

    def clean_billing_ico(self):
        return self.validate_ico_value(self.cleaned_data.get('billing_ico'))

    def clean_billing_dic(self):
        return self.validate_dic_value(self.cleaned_data.get('billing_dic'))

    def clean(self):
        """Cross-validate checkout fields and payment limits."""
        cleaned_data = super().clean()
        billing_different = cleaned_data.get('billing_different')

        if billing_different:
            for field_name in (
                'billing_company_name',
                'billing_ico',
                'billing_street',
                'billing_city',
                'billing_zip_code',
            ):
                if not cleaned_data.get(field_name):
                    self.add_error(field_name, 'Toto pole je povinné pro fakturu na firmu.')

        billing_address_is_delivery = cleaned_data.get('billing_address_is_delivery')
        delivery_different = cleaned_data.get('delivery_different')
        cleaned_data['customer_street'] = cleaned_data.get('shipping_street')
        cleaned_data['customer_city'] = cleaned_data.get('shipping_city')
        cleaned_data['customer_zip_code'] = cleaned_data.get('shipping_zip_code')

        if billing_address_is_delivery and delivery_different:
            self.add_error(
                'delivery_different',
                'Zvolte pouze jednu dodací adresu.',
            )

        if billing_address_is_delivery and not billing_different:
            self.add_error(
                'billing_address_is_delivery',
                'Tuto volbu lze použít pouze při faktuře na firmu.',
            )

        if delivery_different:
            for field_name in (
                'delivery_street',
                'delivery_city',
                'delivery_zip_code',
            ):
                if not cleaned_data.get(field_name):
                    self.add_error(field_name, 'Toto pole je povinné pro jinou dodací adresu.')
            cleaned_data['shipping_street'] = cleaned_data.get('delivery_street')
            cleaned_data['shipping_city'] = cleaned_data.get('delivery_city')
            cleaned_data['shipping_zip_code'] = cleaned_data.get('delivery_zip_code')
        elif billing_different and billing_address_is_delivery:
            cleaned_data['shipping_street'] = cleaned_data.get('billing_street')
            cleaned_data['shipping_city'] = cleaned_data.get('billing_city')
            cleaned_data['shipping_zip_code'] = cleaned_data.get('billing_zip_code')

        for field_name in (
            'shipping_first_name',
            'shipping_last_name',
            'shipping_street',
            'shipping_city',
            'shipping_zip_code',
        ):
            if not cleaned_data.get(field_name):
                self.add_error(field_name, 'Toto pole je povinné pro doručení objednávky.')

        shipping_method = cleaned_data.get('shipping_method')
        payment_method = cleaned_data.get('payment_method')
        if shipping_method and payment_method:
            total_gross = (
                self.products_total_gross
                + shipping_method.price_gross
                + payment_method.price_gross
            )
            payment_limit = Decimal('5000.00') if self.is_registered else Decimal('1000.00')
            advance_payment_names = ('apple pay', 'google pay', 'platba kartou', 'platba převodem')
            if total_gross > payment_limit and not any(
                name in payment_method.name.lower() for name in advance_payment_names
            ):
                self.add_error(
                    'payment_method',
                    f'Objednávky nad {payment_limit:.0f} Kč lze uhradit pouze platbou předem.',
                )

        return cleaned_data


# ===================== REGISTRATION FORM =====================
class RegistrationForm(PhoneValidationMixin, ZipValidationMixin, CompanyIdValidationMixin, UserCreationForm):
    """Registration form with optional company billing details."""

    email = forms.EmailField(required=True, label='E-mail')
    password1 = forms.CharField(
        label='Heslo',
        strip=False,
        widget=forms.PasswordInput,
        help_text='Heslo musí mít alespoň 8 znaků a nesmí být čistě číselné ani příliš běžné.',
    )
    password2 = forms.CharField(
        label='Potvrzení hesla',
        strip=False,
        widget=forms.PasswordInput,
        help_text='Zadejte stejné heslo znovu pro kontrolu.',
        error_messages={'password_mismatch': 'Zadaná hesla se neshodují.'},
    )
    first_name = forms.CharField(max_length=100, required=True, label='Jméno')
    last_name = forms.CharField(max_length=100, required=True, label='Příjmení')
    phone = forms.CharField(
        max_length=50,
        required=True,
        label='Telefon',
    )
    street = forms.CharField(max_length=255, required=True, label='Ulice a číslo popisné')
    city = forms.CharField(max_length=100, required=True, label='Město')
    zip_code = forms.CharField(
        max_length=20,
        required=True,
        label='PSČ',
    )
    billing_different = forms.BooleanField(required=False, label="Chci fakturu na firmu")
    billing_first_name = forms.CharField(max_length=100, required=False, label='Jméno (kontaktní osoba)')
    billing_last_name = forms.CharField(max_length=100, required=False, label='Příjmení (kontaktní osoba)')
    billing_company_name = forms.CharField(max_length=150, required=False, label='Název firmy')
    billing_ico = forms.CharField(max_length=20, required=False, label='IČO')
    billing_dic = forms.CharField(max_length=20, required=False, label='DIČ')
    billing_street = forms.CharField(
        max_length=255,
        required=False,
        label='Ulice a číslo popisné (fakturační)',
    )
    billing_city = forms.CharField(max_length=100, required=False, label='Město (fakturační)')
    billing_zip_code = forms.CharField(max_length=20, required=False, label='PSČ (fakturační)')

    class Meta:
        model = User
        fields = ['email', 'first_name', 'last_name', 'password1', 'password2']

    def clean_phone(self) -> str:
        return self.validate_phone_value(self.cleaned_data.get('phone'))

    def clean_email(self) -> str:
        """Ensure the email is unique across users."""
        email = self.cleaned_data.get('email').lower()
        if User.objects.filter(email=email).exists():
            raise forms.ValidationError('Uživatel s tímto e-mailem již existuje.')
        return email

    def clean_password2(self):
        """Validate that both password fields match, using our Czech error message."""
        password1 = self.cleaned_data.get('password1')
        password2 = self.cleaned_data.get('password2')
        if password1 and password2 and password1 != password2:
            raise forms.ValidationError(
                self.fields['password2'].error_messages['password_mismatch'],
                code='password_mismatch',
            )
        return password2

    def clean_zip_code(self) -> str:
        return self.validate_zip_value(self.cleaned_data.get('zip_code'))

    def clean_billing_zip_code(self) -> str:
        return self.validate_zip_value(self.cleaned_data.get('billing_zip_code'))

    def clean_billing_ico(self):
        return self.validate_ico_value(self.cleaned_data.get('billing_ico'))

    def clean_billing_dic(self):
        return self.validate_dic_value(self.cleaned_data.get('billing_dic'))

    def clean(self):
        """Require the same company invoice data as checkout when B2B is selected."""
        cleaned_data = super().clean()
        if cleaned_data.get('billing_different'):
            for field_name in (
                'billing_company_name',
                'billing_ico',
                'billing_street',
                'billing_city',
                'billing_zip_code',
            ):
                if not cleaned_data.get(field_name):
                    self.add_error(field_name, 'Toto pole je povinné pro fakturu na firmu.')
        return cleaned_data

    def save(self, commit=True):
        """Create the User with email as username, plus a linked Profile with contact/address data."""
        user = super().save(commit=False)
        user.username = self.cleaned_data['email']
        user.email = self.cleaned_data['email']
        user.first_name = self.cleaned_data['first_name']
        user.last_name = self.cleaned_data['last_name']
        if commit:
            user.save()
            Profile.objects.create(
                user=user,
                phone=self.cleaned_data['phone'],
                street=self.cleaned_data['street'],
                city=self.cleaned_data['city'],
                zip_code=self.cleaned_data['zip_code'],
            )
            if self.cleaned_data['billing_different']:
                CompanyBillingProfile.objects.create(
                    profile=user.profile,
                    contact_first_name=self.cleaned_data['billing_first_name'],
                    contact_last_name=self.cleaned_data['billing_last_name'],
                    company_name=self.cleaned_data['billing_company_name'],
                    ico=self.cleaned_data['billing_ico'],
                    dic=self.cleaned_data['billing_dic'],
                    street=self.cleaned_data['billing_street'],
                    city=self.cleaned_data['billing_city'],
                    zip_code=self.cleaned_data['billing_zip_code'],
                )
        return user


# ===================== PROFILE FORM =====================
class ProfileUpdateForm(PhoneValidationMixin, ZipValidationMixin, CompanyIdValidationMixin, forms.Form):
    """Update a customer's contact, delivery, and optional company billing data."""

    email = forms.EmailField(required=True, label='E-mail')
    first_name = forms.CharField(max_length=100, label='Jméno')
    last_name = forms.CharField(max_length=100, label='Příjmení')
    phone = forms.CharField(
        max_length=50,
        required=True,
        label='Telefon',
    )
    street = forms.CharField(max_length=255, label='Ulice a číslo popisné')
    city = forms.CharField(max_length=100, label='Město')
    zip_code = forms.CharField(max_length=20, label='PSČ')

    billing_different = forms.BooleanField(required=False, label='Chci fakturu na firmu')
    billing_first_name = forms.CharField(max_length=100, required=False, label='Jméno (kontaktní osoba)')
    billing_last_name = forms.CharField(max_length=100, required=False, label='Příjmení (kontaktní osoba)')
    billing_company_name = forms.CharField(max_length=150, required=False, label='Název firmy')
    billing_ico = forms.CharField(max_length=20, required=False, label='IČO')
    billing_dic = forms.CharField(max_length=20, required=False, label='DIČ')
    billing_street = forms.CharField(
        max_length=255,
        required=False,
        label='Ulice a číslo popisné (fakturační)',
    )
    billing_city = forms.CharField(max_length=100, required=False, label='Město (fakturační)')
    billing_zip_code = forms.CharField(max_length=20, required=False, label='PSČ (fakturační)')

    def __init__(self, *args, user=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.user = user

    def clean_email(self):
        email = self.cleaned_data.get('email').lower()
        qs = User.objects.filter(email=email)
        if self.user:
            qs = qs.exclude(pk=self.user.pk)
        if qs.exists():
            raise forms.ValidationError('Uživatel s tímto e-mailem již existuje.')
        return email

    def clean_phone(self) -> str:
        return self.validate_phone_value(self.cleaned_data.get('phone'))

    def clean_zip_code(self) -> str:
        return self.validate_zip_value(self.cleaned_data.get('zip_code'))

    def clean_billing_zip_code(self) -> str:
        return self.validate_zip_value(self.cleaned_data.get('billing_zip_code'))

    def clean_billing_ico(self):
        return self.validate_ico_value(self.cleaned_data.get('billing_ico'))

    def clean_billing_dic(self):
        return self.validate_dic_value(self.cleaned_data.get('billing_dic'))

    def clean(self):
        """Require company invoice data when B2B is selected."""
        cleaned_data = super().clean()
        if cleaned_data.get('billing_different'):
            for field_name in (
                'billing_company_name',
                'billing_ico',
                'billing_street',
                'billing_city',
                'billing_zip_code',
            ):
                if not cleaned_data.get(field_name):
                    self.add_error(field_name, 'Toto pole je povinné pro fakturu na firmu.')
        return cleaned_data
