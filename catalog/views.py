from decimal import Decimal
from django.http import HttpRequest, HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST
from django.contrib import messages
from django.utils.safestring import mark_safe
from django.urls import reverse

from .models import Category, Product
from .forms import CartAddProductForm, QuoteRequestForm
from .cart_utils import calculate_cart_totals


# ===================== CATALOG VIEWS =====================
def product_list(request: HttpRequest) -> HttpResponse:
    """Render active product catalog list with optimized category prefetching."""
    products = Product.objects.filter(is_active=True).select_related('vat_rate', 'category__parent')
    categories = Category.objects.filter(is_active=True).select_related('parent')

    return render(request, 'catalog/product_list.html', {
        'products': products,
        'categories': categories,
    })


def product_detail(request: HttpRequest, slug: str) -> HttpResponse:
    """Render active product detail view by unique slug."""
    product = get_object_or_404(
        Product.objects.select_related('vat_rate', 'category__parent'),
        slug=slug,
        is_active=True
    )
    return render(request, 'catalog/product_detail.html', {
        'product': product,
    })


# ===================== QUOTE VIEWS =====================
def custom_quote(request: HttpRequest) -> HttpResponse:
    """
    Display and process the individual quote request form for bulk orders.

    GET – pre-fill product and quantity from query string.
    POST – validate and save quote request, redirect to product list.
    """
    initial = {}
    if request.method == 'GET':
        product_id = request.GET.get('product')
        quantity = request.GET.get('quantity')
        if product_id:
            initial['product'] = get_object_or_404(Product, id=product_id, is_active=True)
        if quantity:
            initial['quantity'] = quantity

    if request.method == 'POST':
        form = QuoteRequestForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, 'Vaše poptávka byla odeslána. Budeme vás kontaktovat.')
            return redirect('catalog:product_list')
    else:
        form = QuoteRequestForm(initial=initial)

    return render(request, 'catalog/custom_quote.html', {'form': form})


# ===================== CART VIEWS =====================
@require_POST
def add_to_cart(request: HttpRequest, product_id: int) -> HttpResponse:
    """
    Add a product to the cart session or update its quantity.

    Handles both normal POST (redirect) and AJAX (JSON) requests.
    """
    product = get_object_or_404(Product, id=product_id, is_active=True)

    post_data = request.POST.copy()
    if 'quantity' not in post_data:
        post_data['quantity'] = 1
    if 'override' not in post_data:
        post_data['override'] = False

    form = CartAddProductForm(post_data, product_stock=product.stock)

    if form.is_valid():
        cd = form.cleaned_data
        quantity = cd['quantity']
        override = cd['override']

        cart = request.session.get('cart', {})
        product_key = str(product.id)

        if override:
            cart[product_key] = quantity
        else:
            cart[product_key] = cart.get(product_key, 0) + quantity

        request.session['cart'] = cart
        request.session.modified = True

        items, total_qty, total_net, total_gross = calculate_cart_totals(cart)

        stock_warning = None
        is_overstock = quantity > product.stock

        if product.stock == 0:
            stock_warning = "Zboží není skladem. Předpokládaná dodací lhůta 3–5 pracovních dnů."
        elif is_overstock:
            stock_warning = f"Požadované množství ({quantity}) přesahuje skladové zásoby ({product.stock}). Dodací lhůta může být prodloužena."

        if request.headers.get('x-requested-with') == 'XMLHttpRequest':
            item_subtotal = product.price_gross * quantity if quantity > 0 else Decimal('0.00')
            return JsonResponse({
                'success': True,
                'message': f'Produkt "{product.name}" byl přidán do košíku.',
                'product_name': product.name,
                'cart_total_quantity': total_qty,
                'total_gross': f"{total_gross:.2f}",
                'total_net': f"{total_net:.2f}",
                'item_subtotal': f"{item_subtotal:.2f}",
                'item_quantity': quantity,
                'stock_warning': stock_warning,
                'is_overstock': is_overstock,
                'stock': product.stock,
            })

        messages.success(request, f'Produkt "{product.name}" byl přidán do košíku.')
        return redirect('catalog:cart_detail')

    raw_quantity = request.POST.get('quantity', '1')
    quote_url = reverse('catalog:custom_quote') + f'?product={product.id}&quantity={raw_quantity}'

    if request.headers.get('x-requested-with') == 'XMLHttpRequest':
        error_msg = "Opravte prosím chyby ve formuláři."
        response_data = {'success': False, 'error': error_msg}

        if 'quantity' in form.errors:
            error_msg = form.errors['quantity'][0]
            response_data = {
                'success': False,
                'error': error_msg,
                'quote_url': quote_url,
                'is_over_limit': True,
                'over_limit_message': (
                    f"Pro objednávky nad 99 ks (vámi zadaných {raw_quantity} ks) "
                    "je nutné individuální posouzení.<br><br>"
                    "Přejděte prosím na formulář nezávazné poptávky.<br><br>"
                    "Při objednávce bude vyžadována platba předem a delší dodací lhůta."
                ),
            }
        elif 'overstock_confirmed' in form.errors:
            error_msg = form.errors['overstock_confirmed'][0]
            response_data = {'success': False, 'error': error_msg}

        return JsonResponse(response_data, status=400)

    error_msg = "Opravte prosím chyby ve formuláři."
    if 'quantity' in form.errors:
        error_msg = form.errors['quantity'][0]
        error_msg += f' <a href="{quote_url}">Přejít na poptávkový formulář</a>'
    elif 'overstock_confirmed' in form.errors:
        error_msg = form.errors['overstock_confirmed'][0]
    messages.error(request, mark_safe(error_msg))

    # Determine where to redirect based on source of request
    if request.POST.get('from_cart'):
        redirect_url = reverse('catalog:cart_detail')
    else:
        redirect_url = reverse('catalog:product_detail', args=[product.slug])

    error_msg = "Opravte prosím chyby ve formuláři."
    if 'quantity' in form.errors:
        error_msg = form.errors['quantity'][0]
        error_msg += f' <a href="{quote_url}">Přejít na poptávkový formulář</a>'
    elif 'overstock_confirmed' in form.errors:
        error_msg = form.errors['overstock_confirmed'][0]

    messages.error(request, mark_safe(error_msg))
    return redirect(redirect_url)


@require_POST
def cart_remove(request: HttpRequest, product_id: int) -> HttpResponse:
    """
    Remove a specific product completely from the session cart.

    Works for both normal POST (redirect) and AJAX (JSON) requests.
    """
    product = get_object_or_404(Product, id=product_id)
    cart = request.session.get('cart', {})
    product_key = str(product.id)

    if product_key in cart:
        del cart[product_key]
        request.session['cart'] = cart
        request.session.modified = True

    items, total_qty, total_net, total_gross = calculate_cart_totals(cart)

    if request.headers.get('x-requested-with') == 'XMLHttpRequest':
        return JsonResponse({
            'success': True,
            'cart_total_quantity': total_qty,
            'total_gross': f"{total_gross:.2f}",
            'total_net': f"{total_net:.2f}",
        })

    return redirect('catalog:cart_detail')


def cart_detail(request: HttpRequest) -> HttpResponse:
    """
    Render the shopping cart detail view with full item details and totals.
    """
    cart = request.session.get('cart', {})
    items, total_quantity, total_net, total_gross = calculate_cart_totals(cart)

    return render(request, 'catalog/cart_detail.html', {
        'items': items,
        'total_quantity': total_quantity,
        'total_net': total_net,
        'total_gross': total_gross,
    })
