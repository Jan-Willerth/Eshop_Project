from decimal import Decimal
from django.http import HttpRequest, HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST
from django.contrib import messages

from .models import Category, Product
from .forms import CartAddProductForm
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


# ===================== CART VIEWS =====================
@require_POST
def add_to_cart(request: HttpRequest, product_id: int) -> HttpResponse:
    """
    Add a product to the cart session or update its quantity.

    Handles both normal POST (redirect) and AJAX (JSON) requests.
    """
    product = get_object_or_404(Product, id=product_id, is_active=True)

    # Ensure required fields are present in POST
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

        # Recalculate entire cart for consistent totals
        items, total_qty, total_net, total_gross = calculate_cart_totals(cart)

        # Prepare optional stock warning for the current product
        stock_warning = None
        is_overstock = quantity > product.stock
        if product.stock == 0:
            stock_warning = "Zboží není skladem. Předpokládaná dodací lhůta 3–5 pracovních dnů."
        elif is_overstock:
            stock_warning = f"Požadované množství ({quantity}) přesahuje skladové zásoby ({product.stock}). Dodací lhůta může být prodloužena."

        # AJAX response
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

        # Normal POST – flash message and redirect to cart
        messages.success(request, f'Produkt "{product.name}" byl přidán do košíku.')
        return redirect('catalog:cart_detail')

    # Invalid form (e.g. overstock not confirmed)
    if request.headers.get('x-requested-with') == 'XMLHttpRequest':
        # Extract overstock error if present
        error_msg = "Pro objednání vyššího množství než je skladem musíte potvrdit delší dodací lhůtu."
        if 'overstock_confirmed' in form.errors:
            error_msg = form.errors['overstock_confirmed'][0]
        return JsonResponse({'success': False, 'error': error_msg}, status=400)

    # Normal POST error – flash and redirect back to product detail
    messages.error(
        request,
        'Pro objednání vyššího množství než je skladem musíte potvrdit delší dodací lhůtu.'
    )
    return redirect('catalog:product_detail', slug=product.slug)


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

    # AJAX response
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
    Render the shopping cart detail view with full item details, totals,
    and bulk item status (>50 pcs) for custom quotes.
    """
    cart = request.session.get('cart', {})
    items, total_quantity, total_net, total_gross = calculate_cart_totals(cart)

    # Check if any item quantity exceeds 50 for special handling
    has_bulk_items = any(item['quantity'] > 50 for item in items)

    return render(request, 'catalog/cart_detail.html', {
        'items': items,
        'total_quantity': total_quantity,
        'total_net': total_net,
        'total_gross': total_gross,
        'has_bulk_items': has_bulk_items,
    })
