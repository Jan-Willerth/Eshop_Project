import re
from django import forms
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth.models import User
from .models import QuoteRequest, ShippingMethod, PaymentMethod, Profile


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
class QuoteRequestForm(forms.ModelForm):
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
            'phone': forms.TextInput(attrs={'class': 'form-control'}),
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


# ===================== ORDER FORM =====================
class OrderForm(forms.Form):
    """Validate checkout data, requiring billing details only when billing_different is checked."""

    customer_email = forms.EmailField(label='E-mail')
    customer_phone = forms.CharField(max_length=50, label='Telefon')

    shipping_first_name = forms.CharField(max_length=100, label='Jméno')
    shipping_last_name = forms.CharField(max_length=100, label='Příjmení')
    shipping_street = forms.CharField(max_length=255, label='Ulice a číslo popisné')
    shipping_city = forms.CharField(max_length=100, label='Město')
    shipping_zip_code = forms.CharField(max_length=20, label='PSČ')

    shipping_method = ShippingMethodChoiceField(queryset=ShippingMethod.objects.filter(is_active=True),
                                                label='Způsob dopravy')
    payment_method = PaymentMethodChoiceField(queryset=PaymentMethod.objects.filter(is_active=True),
                                              label='Způsob platby')

    billing_different = forms.BooleanField(required=False, label="Chci fakturu na firmu")
    billing_first_name = forms.CharField(max_length=100, required=False, label='Jméno (kontaktní osoba)')
    billing_last_name = forms.CharField(max_length=100, required=False, label='Příjmení (kontaktní osoba)')
    billing_company_name = forms.CharField(max_length=150, required=False, label='Název firmy')
    billing_ico = forms.CharField(
        max_length=20,
        required=False,
        label='IČO',
        widget=forms.TextInput(
            attrs={'pattern': r'\d{8}', 'maxlength': '8', 'title': 'IČO musí obsahovat přesně 8 číslic.'})
    )
    billing_dic = forms.CharField(max_length=20, required=False, label='DIČ')
    billing_street = forms.CharField(max_length=255, required=False, label='Ulice a číslo popisné (fakturační)')
    billing_city = forms.CharField(max_length=100, required=False, label='Město (fakturační)')
    billing_zip_code = forms.CharField(max_length=20, required=False, label='PSČ (fakturační)')

    def clean_shipping_first_name(self) -> str:
        """Capitalize the shipping first name."""
        return self.cleaned_data.get('shipping_first_name', '').strip().capitalize()

    def clean_shipping_last_name(self) -> str:
        """Capitalize the shipping last name."""
        return self.cleaned_data.get('shipping_last_name', '').strip().capitalize()

    def clean(self):
        """Require billing_company_name, billing_ico, and billing address when billing_different is checked."""
        cleaned_data = super().clean()

        if cleaned_data.get('billing_different'):
            required_billing_fields = [
                'billing_company_name', 'billing_ico',
                'billing_street', 'billing_city', 'billing_zip_code',
            ]
            for field_name in required_billing_fields:
                if not cleaned_data.get(field_name):
                    self.add_error(field_name, 'Toto pole je povinné pro fakturu na firmu.')

            billing_ico = cleaned_data.get('billing_ico')
            if billing_ico and not re.fullmatch(r'\d{8}', billing_ico):
                self.add_error('billing_ico', 'IČO musí obsahovat přesně 8 číslic.')

        return cleaned_data


# ===================== REGISTRATION FORM =====================
class RegistrationForm(UserCreationForm):
    """Registration form based on Django's UserCreationForm, using email as the username, with contact/address."""

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
        widget=forms.TextInput(attrs={
            'inputmode': 'tel',
            'pattern': r'\+?[0-9 ]{9,15}',
            'maxlength': '15',
            'title': 'Zadejte telefonní číslo (např. 732258910 nebo +420732258910).',
        })
    )
    street = forms.CharField(max_length=255, required=True, label='Ulice a číslo popisné')
    city = forms.CharField(max_length=100, required=True, label='Město')
    zip_code = forms.CharField(
        max_length=20,
        required=True,
        label='PSČ',
        widget=forms.TextInput(attrs={
            'inputmode': 'numeric',
            'pattern': r'\d{5}',
            'maxlength': '5',
            'title': 'PSČ musí obsahovat přesně 5 číslic (bez mezery).',
        })
    )

    class Meta:
        model = User
        fields = ['email', 'first_name', 'last_name', 'password1', 'password2']

    def clean_email(self) -> str:
        """Ensure the email is unique across users."""
        email = self.cleaned_data.get('email')
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
        return user
