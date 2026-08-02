from decimal import Decimal
from typing import Dict, Any, List

from django.http import HttpRequest, HttpResponse, HttpResponseRedirect
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from .models import Category, Product


# ===================== CATALOG VIEWS =====================
def product_list(request: HttpRequest) -> HttpResponse:
    # Select product category and its parent category in one DB query
    products = Product.objects.filter(is_active=True).select_related('vat_rate', 'category__parent')
    categories = Category.objects.filter(is_active=True).select_related('parent')

    return render(request, 'catalog/product_list.html', {
        'products': products,
        'categories': categories,
    })


def product_detail(request: HttpRequest, slug: str) -> HttpResponse:
    # Fetch product with its category and parent category
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
def add_to_cart(request: HttpRequest, product_id: int) -> HttpResponseRedirect:
    """Add a product to the cart session with variable quantity (POST only)."""
    # Validate product existence and active status
    product = get_object_or_404(Product, id=product_id, is_active=True)
    cart: Dict[str, int] = request.session.get('cart', {})
    key = str(product_id)

    # Parse and validate requested quantity from POST payload
    try:
        requested_qty = int(request.POST.get('quantity', 1))
        if requested_qty < 1:
            requested_qty = 1
    except (ValueError, TypeError):
        requested_qty = 1

    # Calculate new total quantity
    current_qty = cart.get(key, 0)
    new_qty = current_qty + requested_qty

    # Cap quantity at available inventory level
    if new_qty > product.stock:
        new_qty = product.stock

    cart[key] = new_qty
    request.session['cart'] = cart

    return redirect(request.META.get('HTTP_REFERER', 'catalog:cart_detail'))


def cart_detail(request: HttpRequest) -> HttpResponse:
    """Display cart contents with optimized DB queries and aggregated totals."""
    cart: Dict[str, int] = request.session.get('cart', {})

    # Safely extract all valid numeric product IDs from session keys
    product_ids: List[int] = [int(pid) for pid in cart.keys() if pid.isdigit()]

    # Fetch all active cart products in a single database query
    products = Product.objects.filter(
        id__in=product_ids,
        is_active=True
    ).select_related('vat_rate', 'category__parent')

    # Map products by ID for O(1) in-memory lookup
    products_by_id: Dict[int, Product] = {p.id: p for p in products}

    items: List[Dict[str, Any]] = []
    total_net: Decimal = Decimal('0.00')
    total_gross: Decimal = Decimal('0.00')
    total_quantity: int = 0
    session_modified: bool = False

    # Process cart items without additional DB queries
    for product_id_str, quantity in list(cart.items()):
        if not product_id_str.isdigit():
            del cart[product_id_str]
            session_modified = True
            continue

        product_id: int = int(product_id_str)
        product: Product | None = products_by_id.get(product_id)

        # Skip and clean up products that were deactivated or removed from DB
        if not product:
            del cart[product_id_str]
            session_modified = True
            continue

        subtotal_net: Decimal = product.price_net * quantity
        subtotal_gross: Decimal = product.price_gross * quantity

        total_net += subtotal_net
        total_gross += subtotal_gross
        total_quantity += quantity

        items.append({
            'product': product,
            'quantity': quantity,
            'subtotal_net': subtotal_net,
            'subtotal_gross': subtotal_gross,
        })

    # Save cleaned session state if any stale items were purged
    if session_modified:
        request.session['cart'] = cart

    context = {
        'items': items,
        'total_net': total_net,
        'total_gross': total_gross,
        'total_quantity': total_quantity,
    }
    return render(request, 'catalog/cart_detail.html', context)
