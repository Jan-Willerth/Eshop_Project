from django.shortcuts import get_object_or_404, render

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
