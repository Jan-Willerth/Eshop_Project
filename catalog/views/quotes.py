from django.contrib import messages
from django.http import HttpRequest, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render

from ..forms import QuoteRequestForm
from ..models import Product


# ===================== QUOTE VIEWS =====================
def custom_quote(request: HttpRequest) -> HttpResponse:
    """Display and process the custom quote request form for bulk orders."""
    initial = {}
    if request.method == 'GET':
        product_id = request.GET.get('product')
        quantity = request.GET.get('quantity')
        if product_id:
            initial['product'] = get_object_or_404(
                Product, id=product_id, is_active=True
            )
        if quantity:
            initial['quantity'] = quantity

    if request.method == 'POST':
        form = QuoteRequestForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(
                request,
                'Vaše poptávka byla odeslána. Budeme vás kontaktovat.',
            )
            return redirect('catalog:homepage')
    else:
        form = QuoteRequestForm(initial=initial)

    return render(request, 'catalog/custom_quote.html', {'form': form})
