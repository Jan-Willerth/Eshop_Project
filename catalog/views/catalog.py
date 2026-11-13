from django.http import HttpRequest, HttpResponse
from django.shortcuts import get_object_or_404, render

from ..models import Category, Product


# ===================== CATALOG VIEWS =====================
def homepage(request):
    """Homepage showing top-level product categories."""
    categories = Category.objects.filter(parent=None, is_active=True)
    return render(request, 'catalog/homepage.html', {'categories': categories})


def product_list(request: HttpRequest) -> HttpResponse:
    """Render the product catalog. Staff with change permission also
    see inactive products so they can reactivate them.
    """
    if request.user.has_perm('catalog.change_product'):
        products = Product.objects.select_related('vat_rate', 'category__parent')
    else:
        products = (
            Product.objects.filter(is_active=True)
            .select_related('vat_rate', 'category__parent')
        )

    categories = Category.objects.filter(is_active=True).select_related('parent')

    return render(request, 'catalog/product_list.html', {
        'products': products,
        'categories': categories,
    })


def category_detail(request, slug):
    """Display subcategories of the selected category, or products
    if the category has no subcategories.
    """
    category = get_object_or_404(Category, slug=slug, is_active=True)

    subcategories = category.subcategories.filter(is_active=True)

    if subcategories.exists():
        return render(request, 'catalog/category_detail.html', {
            'category': category,
            'subcategories': subcategories,
        })

    if request.user.has_perm('catalog.change_product'):
        products = (
            Product.objects.filter(category=category)
            .select_related('vat_rate', 'category__parent')
        )
    else:
        products = (
            Product.objects.filter(category=category, is_active=True)
            .select_related('vat_rate', 'category__parent')
        )

    return render(request, 'catalog/product_list.html', {
        'products': products,
        'category': category,
    })


def product_detail(request: HttpRequest, slug: str) -> HttpResponse:
    """Render the product detail page. Staff with change permission
    can also view inactive products.
    """
    queryset = Product.objects.select_related('vat_rate', 'category__parent')
    if not request.user.has_perm('catalog.change_product'):
        queryset = queryset.filter(is_active=True)

    product = get_object_or_404(queryset, slug=slug)
    return render(request, 'catalog/product_detail.html', {'product': product})
