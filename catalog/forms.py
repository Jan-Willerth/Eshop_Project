from django import forms
from .models import QuoteRequest, ShippingMethod, PaymentMethod


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

    customer_email = forms.EmailField()
    customer_phone = forms.CharField(max_length=50)

    shipping_first_name = forms.CharField(max_length=100)
    shipping_last_name = forms.CharField(max_length=100)
    shipping_street = forms.CharField(max_length=255)
    shipping_city = forms.CharField(max_length=100)
    shipping_zip_code = forms.CharField(max_length=20)

    shipping_method = forms.ModelChoiceField(queryset=ShippingMethod.objects.filter(is_active=True))
    payment_method = forms.ModelChoiceField(queryset=PaymentMethod.objects.filter(is_active=True))

    billing_different = forms.BooleanField(required=False, label="Chci fakturu na firmu")
    billing_first_name = forms.CharField(max_length=100, required=False)
    billing_last_name = forms.CharField(max_length=100, required=False)
    billing_company_name = forms.CharField(max_length=150, required=False)
    billing_ico = forms.CharField(max_length=20, required=False)
    billing_dic = forms.CharField(max_length=20, required=False)
    billing_street = forms.CharField(max_length=255, required=False)
    billing_city = forms.CharField(max_length=100, required=False)
    billing_zip_code = forms.CharField(max_length=20, required=False)

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

        return cleaned_data
