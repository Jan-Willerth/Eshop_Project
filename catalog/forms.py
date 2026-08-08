from django import forms


# ===================== CART FORMS =====================
class CartAddProductForm(forms.Form):
    """Form for validating product quantity, cart update mode, and overstock confirmation."""

    quantity = forms.CharField(
        max_length=10,
        required=False,
        initial='1',
        widget=forms.TextInput(attrs={
            'class': 'form-control text-center',
            'min': '1',
            'max': '50',
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
        """Pass product_stock to dynamically validate overstock acceptance."""
        super().__init__(*args, **kwargs)
        self.product_stock = product_stock

    def clean_quantity(self) -> int:
        """
        Parse quantity from string input, defaulting to 1 for any invalid value.
        Valid range: 1–50.
        """
        raw = self.cleaned_data.get('quantity', '').strip()
        try:
            qty = int(raw)
        except (ValueError, TypeError):
            return 1  # fallback for empty or non-numeric input

        if qty < 1:
            return 1
        if qty > 50:
            raise forms.ValidationError(
                'Maximální množství na jednu položku je 50 ks. '
                'Pro větší objednávky nás prosím kontaktujte.',
                code='max_value'
            )
        return qty

    def clean(self):
        """Ensure overstock confirmation checkbox is checked when quantity exceeds stock."""
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
