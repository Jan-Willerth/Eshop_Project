from django.http import HttpRequest, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from .models import Category, Product
from .forms import CartAddProductForm


# ===================== CATALOG VIEWS =====================
def product_list(request: HttpRequest) -> HttpResponse:
    """Render active product catalog list with optimized category prefetching."""
    # Select product category and its parent category in one DB query
    products = Product.objects.filter(is_active=True).select_related('vat_rate', 'category__parent')
    categories = Category.objects.filter(is_active=True).select_related('parent')

    return render(request, 'catalog/product_list.html', {
        'products': products,
        'categories': categories,
    })


def product_detail(request: HttpRequest, slug: str) -> HttpResponse:
    """Render active product detail view by unique slug."""
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
def add_to_cart(request: HttpRequest, product_id: int) -> HttpResponse:
    """Add a product to the cart session or update its quantity using validation form."""
    # Fetch active product or return 404
    product = get_object_or_404(Product, id=product_id, is_active=True)
    form = CartAddProductForm(request.POST)

    # Validate quantity payload or set safe defaults
    if form.is_valid():
        quantity = form.cleaned_data['quantity']
        override = form.cleaned_data['override']
    else:
        quantity = 1
        override = False

    cart = request.session.get('cart', {})
    product_key = str(product.id)

    # Update item quantity or override existing value in cart
    if override:
        cart[product_key] = quantity
    else:
        cart[product_key] = cart.get(product_key, 0) + quantity

    # Save updated cart back to session
    request.session['cart'] = cart
    request.session.modified = True

    return redirect('catalog:cart_detail')


@require_POST
def cart_remove(request: HttpRequest, product_id: int) -> HttpResponse:
    """Remove a specific product completely from the session cart."""
    # Fetch product and cart session data
    product = get_object_or_404(Product, id=product_id)
    cart = request.session.get('cart', {})
    product_key = str(product.id)

    # Remove product from cart if present and persist session
    if product_key in cart:
        del cart[product_key]
        request.session['cart'] = cart
        request.session.modified = True

    return redirect('catalog:cart_detail')


def cart_detail(request: HttpRequest) -> HttpResponse:
    """Render the shopping cart detail view."""
    # Fetch shopping cart contents from current session
    cart = request.session.get('cart', {})

    # Temporary basic render for cart detail view and test suite compatibility
    return render(request, 'catalog/cart_detail.html', {'cart': cart})
