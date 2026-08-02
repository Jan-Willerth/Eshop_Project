from django.shortcuts import get_object_or_404, render, redirect

from .models import Category, Product


def product_list(request):
    # Select product category and its parent category in one DB query
    products = Product.objects.filter(is_active=True).select_related('vat_rate', 'category__parent')
    categories = Category.objects.filter(is_active=True)

    return render(request, 'catalog/product_list.html', {
        'products': products,
        'categories': categories,
    })


def product_detail(request, slug):
    # Fetch product with its category and parent category
    product = get_object_or_404(
        Product.objects.select_related('vat_rate', 'category__parent'),
        slug=slug,
        is_active=True
    )
    return render(request, 'catalog/product_detail.html', {
        'product': product,
    })


def add_to_cart(request, product_id):
    """Add product to cart session or increase quantity."""
    # Validate product exists and is active
    product = get_object_or_404(Product, id=product_id, is_active=True)
    cart = request.session.get('cart', {})
    key = str(product_id)

    # Increase quantity (or add new)
    if key in cart:
        cart[key] += 1
    else:
        cart[key] = 1

    # Optional: check stock limit
    if cart[key] > product.stock:
        cart[key] = product.stock  # cap at stock

    request.session['cart'] = cart
    return redirect(request.META.get('HTTP_REFERER', 'catalog:product_list'))


def cart_detail(request):
    """Display cart contents with product details and totals."""
    cart = request.session.get('cart', {})
    items = []
    total_net = 0
    total_gross = 0
    total_quantity = 0

    for product_id, quantity in cart.items():
        product = get_object_or_404(Product, id=int(product_id), is_active=True)
        subtotal_net = product.price_net * quantity
        subtotal_gross = product.price_gross * quantity
        total_net += subtotal_net
        total_gross += subtotal_gross
        total_quantity += quantity
        items.append({
            'product': product,
            'quantity': quantity,
            'subtotal_net': subtotal_net,
            'subtotal_gross': subtotal_gross,
        })

    context = {
        'items': items,
        'total_net': total_net,
        'total_gross': total_gross,
        'total_quantity': total_quantity,
    }
    return render(request, 'catalog/cart_detail.html', context)
