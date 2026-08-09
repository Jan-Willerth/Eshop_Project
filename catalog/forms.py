from django import forms
from .models import QuoteRequest


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
