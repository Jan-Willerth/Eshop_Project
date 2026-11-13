from django.contrib.auth.decorators import login_required, permission_required

from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from ..forms import (
    ProductForm
)
from ..models import (
    Product,
)


# ===================== PRODUCT MANAGEMENT (STAFF) =====================
@login_required(login_url='catalog:login')
@permission_required('catalog.add_product', raise_exception=True)
def product_create(request):
    """Staff-only view for adding a new product to the catalog."""
    if request.method == 'POST':
        form = ProductForm(request.POST, request.FILES)
        if form.is_valid():
            form.save()
            return redirect('catalog:homepage')
    else:
        form = ProductForm()

    return render(request, 'catalog/product_form.html', {'form': form})


@login_required(login_url='catalog:login')
@permission_required('catalog.change_product', raise_exception=True)
def product_update(request, pk):
    """Staff-only view for editing a product, including its stock quantity."""
    product = get_object_or_404(Product, pk=pk)

    if request.method == 'POST':
        form = ProductForm(request.POST, request.FILES, instance=product)
        if form.is_valid():
            form.save()
            return redirect('catalog:homepage')
    else:
        form = ProductForm(instance=product)

    return render(request, 'catalog/product_form.html', {'form': form, 'product': product})


@login_required(login_url='catalog:login')
@permission_required('catalog.delete_product', raise_exception=True)
@require_POST
def product_delete(request, pk):
    """Staff-only view for deactivating a product (soft delete). A hard
    delete from the database is intentionally never performed here, since a
    Product referenced by an existing OrderItem is protected and would raise
    ProtectedError, and history/PDF invoices should stay intact either way.
    """
    product = get_object_or_404(Product, pk=pk)
    product.is_active = False
    product.save()
    return redirect('catalog:homepage')
