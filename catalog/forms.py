from django import forms

from django import forms


# ===================== CART FORMS =====================
class CartAddProductForm(forms.Form):
    """Form for validating product quantity and cart update mode."""

    # Quantity input with custom HTML attributes and localized validation errors
    quantity = forms.IntegerField(
        min_value=1,
        max_value=50,
        initial=1,
        widget=forms.NumberInput(attrs={
            'class': 'form-control text-center',
            'min': '1',
            'max': '50',
        }),
        error_messages={
            'invalid': 'Zadejte platné číslo.',
            'min_value': 'Množství musí být alespoň 1 ks.',
            'max_value': 'Pro objednávky nad 50 ks nás prosím kontaktujte přímo pro individuální nabídku.',
        }
    )

    # Flag to determine whether to add to existing quantity or override it
    override = forms.BooleanField(
        required=False,
        initial=False,
        widget=forms.HiddenInput
    )

    def clean_quantity(self) -> int:
        """Fallback to default 1 if invalid or empty quantity is supplied."""
        quantity = self.cleaned_data.get('quantity')

        # Ensure minimum quantity of 1 if clean data is missing or out of bounds
        if not quantity or quantity < 1:
            return 1

        return quantity
