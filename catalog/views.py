from decimal import Decimal
from django.http import HttpRequest, HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from .models import Category, Product
from .forms import CartAddProductForm


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


# ===================== CART VIEWS =====================
def _calculate_cart_totals(cart: dict) -> tuple:
    """
    Helper function to calculate cart totals.
    Returns: (items, total_quantity, total_net, total_gross)
    """
    product_ids = [int(pid) for pid in cart.keys() if pid.isdigit()]
    products = Product.objects.filter(id__in=product_ids, is_active=True)
    products_dict = {p.id: p for p in products}

    items = []
    total_quantity = 0
    total_net = Decimal('0.00')
    total_gross = Decimal('0.00')

    for product_id_str, quantity in cart.items():
        if not product_id_str.isdigit():
            continue
        product_id = int(product_id_str)
        product = products_dict.get(product_id)
        if product is None:
            continue

        quantity = int(quantity) if isinstance(quantity, int) else 1
        if quantity < 1:
            quantity = 1

        item_net = product.price_net * quantity
        item_gross = product.price_gross * quantity

        items.append({
            'product': product,
            'quantity': quantity,
            'subtotal_net': item_net,
            'subtotal_gross': item_gross,
        })

        total_quantity += quantity
        total_net += item_net
        total_gross += item_gross

    return items, total_quantity, total_net, total_gross


@require_POST
def add_to_cart(request: HttpRequest, product_id: int) -> HttpResponse:
    """Add a product to the cart session or update its quantity using validation form."""
    product = get_object_or_404(Product, id=product_id, is_active=True)
    form = CartAddProductForm(request.POST, product_stock=product.stock)

    if form.is_valid():
        cd = form.cleaned_data
        quantity = cd['quantity']
        override = cd['override']
    else:
        messages.error(
            request,
            'Pro objednání vyššího množství než je skladem musíte potvrdit delší dodací lhůtu.'
        )
        return redirect('catalog:product_detail', slug=product.slug)

    cart = request.session.get('cart', {})
    product_key = str(product.id)

    if override:
        cart[product_key] = quantity
    else:
        cart[product_key] = cart.get(product_key, 0) + quantity

    request.session['cart'] = cart
    request.session.modified = True

    return redirect('catalog:cart_detail')


@require_POST
def cart_remove(request: HttpRequest, product_id: int) -> HttpResponse:
    """Remove a specific product completely from the session cart."""
    product = get_object_or_404(Product, id=product_id)
    cart = request.session.get('cart', {})
    product_key = str(product.id)

    if product_key in cart:
        del cart[product_key]
        request.session['cart'] = cart
        request.session.modified = True

    return redirect('catalog:cart_detail')


def cart_detail(request: HttpRequest) -> HttpResponse:
    """
    Render the shopping cart detail view with full item details, totals,
    and bulk item status (>50 pcs) for custom quotes.
    """
    cart = request.session.get('cart', {})

    # Použití pomocné funkce pro získání položek a součtů
    items, total_quantity, total_net, total_gross = _calculate_cart_totals(cart)

    # Detekce, zda jakákoliv položka v košíku přesahuje 50 ks
    has_bulk_items = any(item['quantity'] > 50 for item in items)

    return render(request, 'catalog/cart_detail.html', {
        'items': items,
        'total_quantity': total_quantity,
        'total_net': total_net,
        'total_gross': total_gross,
        'has_bulk_items': has_bulk_items,
    })


# ===================== AJAX CART VIEWS =====================
def add_to_cart_ajax(request: HttpRequest, product_id: int) -> JsonResponse:
    """AJAX endpoint for adding product to cart - returns JSON."""
    product = get_object_or_404(Product, id=product_id, is_active=True)
    form = CartAddProductForm(request.POST)

    if form.is_valid():
        quantity = form.cleaned_data['quantity']
        override = form.cleaned_data['override']
    else:
        quantity = 1
        override = True

    cart = request.session.get('cart', {})
    product_key = str(product.id)

    if override:
        cart[product_key] = quantity
    else:
        cart[product_key] = cart.get(product_key, 0) + quantity

    request.session['cart'] = cart
    request.session.modified = True

    # Calculate total quantity
    total_quantity = sum(
        qty for key, qty in cart.items()
        if key.isdigit() and isinstance(qty, int)
    )

    stock_warning = None
    if product.stock == 0:
        stock_warning = "Zboží není skladem. Předpokládaná dodací lhůta 3–5 pracovních dnů."
    elif product.stock < quantity:
        stock_warning = (f"Požadované množství ({quantity}) přesahuje skladové zásoby ({product.stock})."
                         f" Dodací lhůta může být prodloužena.")

    return JsonResponse({
        'success': True,
        'cart_total_quantity': total_quantity,
        'item_quantity': cart[product_key],
        'stock_warning': stock_warning,
    })


@require_POST
def update_cart_ajax(request: HttpRequest, product_id: int) -> JsonResponse:
    """AJAX endpoint for updating quantity - returns JSON with recalculated totals."""
    product = get_object_or_404(Product, id=product_id, is_active=True)

    try:
        quantity = int(request.POST.get('quantity', 1))
        if quantity < 1:
            quantity = 1
    except (ValueError, TypeError):
        return JsonResponse({
            'success': False,
            'error': 'Quantity must be a positive integer.'
        }, status=400)

    cart = request.session.get('cart', {})
    product_key = str(product.id)

    if quantity < 1:
        if product_key in cart:
            del cart[product_key]
    else:
        cart[product_key] = quantity

    request.session['cart'] = cart
    request.session.modified = True

    items, total_quantity, total_net, total_gross = _calculate_cart_totals(cart)

    stock_warning = None
    if product.stock == 0:
        stock_warning = "Zboží není skladem. Předpokládaná dodací lhůta 3–5 pracovních dnů."
    elif product.stock < quantity:
        stock_warning = f"Požadované množství ({quantity}) přesahuje skladové zásoby ({product.stock}). Dodací lhůta může být prodloužena."

    item_subtotal = Decimal(product.price_gross * quantity) if quantity > 0 else Decimal('0.00')

    return JsonResponse({
        'success': True,
        'cart_total_quantity': total_quantity,
        'total_gross': f"{total_gross:.2f}",
        'total_net': f"{total_net:.2f}",
        'item_subtotal': f"{item_subtotal:.2f}",
        'item_quantity': quantity,
        'stock_warning': stock_warning,
    })


@require_POST
def remove_from_cart_ajax(request: HttpRequest, product_id: int) -> JsonResponse:
    """AJAX endpoint for removing item - returns JSON with updated totals."""
    product = get_object_or_404(Product, id=product_id)
    cart = request.session.get('cart', {})
    product_key = str(product.id)

    if product_key in cart:
        del cart[product_key]
        request.session['cart'] = cart
        request.session.modified = True

    items, total_quantity, total_net, total_gross = _calculate_cart_totals(cart)

    return JsonResponse({
        'success': True,
        'cart_total_quantity': total_quantity,
        'total_gross': f"{total_gross:.2f}",
        'total_net': f"{total_net:.2f}",
    })
