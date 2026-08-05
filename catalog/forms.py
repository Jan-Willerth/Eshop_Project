from django import forms


# ===================== CART FORMS =====================
class CartAddProductForm(forms.Form):
    """Form for validating product quantity, cart update mode, and overstock confirmation."""

    quantity = forms.IntegerField(
        min_value=1,
        initial=1,
        widget=forms.NumberInput(attrs={
            'class': 'form-control text-center',
            'min': '1',
        }),
        error_messages={
            'invalid': 'Zadejte platné číslo.',
            'min_value': 'Množství musí být alespoň 1 ks.',
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
        """Fallback to default 1 if invalid or empty quantity is supplied."""
        quantity = self.cleaned_data.get('quantity')
        if not quantity or quantity < 1:
            return 1
        return quantity

    def clean(self):
        cleaned_data = super().clean()
        quantity = cleaned_data.get('quantity') or 0
        confirmed = cleaned_data.get('overstock_confirmed')

        # Pokud uživatel objednává více než je skladem, musí zaškrtnout souhlas
        if quantity > self.product_stock and not confirmed:
            self.add_error(
                'overstock_confirmed',
                f'Poptáváte více kusů, než máme skladem ({self.product_stock} ks). Potvrďte prosím souhlas s delší dodací lhůtou.'
            )
        return cleaned_data
