from decimal import Decimal
from django.http import HttpRequest, HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST
from django.contrib import messages
from django.utils.safestring import mark_safe
from django.urls import reverse
from django.db import transaction

from .models import Category, Product, ShippingMethod, PaymentMethod, OrderStatus, Order, OrderItem
from .forms import CartAddProductForm, QuoteRequestForm, OrderForm
from .cart_utils import calculate_cart_totals, cart_has_unconfirmed_overstock


# ===================== CATALOG VIEWS =====================
def product_list(request: HttpRequest) -> HttpResponse:
    """Render the active product catalog with optimized category prefetching."""
    products = Product.objects.filter(is_active=True).select_related('vat_rate', 'category__parent')
    categories = Category.objects.filter(is_active=True).select_related('parent')

    return render(request, 'catalog/product_list.html', {
        'products': products,
        'categories': categories,
    })


def product_detail(request: HttpRequest, slug: str) -> HttpResponse:
    """Render the product detail page for an active product."""
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
    """Display and process the custom quote request form for bulk orders."""
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
    """Add a product to the cart or update its quantity (AJAX/redirect)."""
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

        overstock_confirmed = cd.get('overstock_confirmed', False)

        if override:
            new_quantity = quantity
        else:
            existing_entry = cart.get(product_key, 0)
            existing_qty = existing_entry.get('quantity', 0) if isinstance(existing_entry, dict) else existing_entry
            new_quantity = existing_qty + quantity

        cart[product_key] = {
            'quantity': new_quantity,
            'overstock_confirmed': overstock_confirmed,
        }

        request.session['cart'] = cart
        request.session.modified = True

        items, total_qty, total_net, total_gross = calculate_cart_totals(cart)

        stock_warning = None
        is_overstock = new_quantity > product.stock

        if product.stock == 0:
            stock_warning = "Zboží není skladem. Předpokládaná dodací lhůta 3–5 pracovních dnů."
        elif is_overstock:
            stock_warning = f"Požadované množství ({new_quantity}) přesahuje skladové zásoby ({product.stock}). Dodací lhůta může být prodloužena."

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
                'item_quantity': new_quantity,
                'stock_warning': stock_warning,
                'is_overstock': is_overstock,
                'overstock_confirmed': overstock_confirmed,
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
            response_data = {
                'success': False,
                'error': error_msg,
                'error_field': 'overstock_confirmed',
                'stock': product.stock,
            }

        return JsonResponse(response_data, status=400)

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
    """Remove a product completely from the session cart (AJAX/redirect)."""
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
    """Render the shopping cart detail view with totals."""
    cart = request.session.get('cart', {})
    items, total_quantity, total_net, total_gross = calculate_cart_totals(cart)

    return render(request, 'catalog/cart_detail.html', {
        'items': items,
        'total_quantity': total_quantity,
        'total_net': total_net,
        'total_gross': total_gross,
        'has_unconfirmed_overstock': cart_has_unconfirmed_overstock(cart),
    })


# ===================== ORDER VIEWS =====================
def checkout(request: HttpRequest) -> HttpResponse:
    """Display and validate the checkout form."""
    cart = request.session.get('cart', {})

    if cart_has_unconfirmed_overstock(cart):
        messages.error(
            request,
            'V košíku máte položky přesahující skladové zásoby. '
            'Pro pokračování je nutné potvrdit souhlas s delší dodací lhůtou.'
        )
        return redirect('catalog:cart_detail')

    if request.method == 'POST':
        form = OrderForm(request.POST)
        if form.is_valid():
            cd = form.cleaned_data
            request.session['pending_order'] = {
                'customer_email': cd['customer_email'],
                'customer_phone': cd['customer_phone'],
                'shipping_first_name': cd['shipping_first_name'],
                'shipping_last_name': cd['shipping_last_name'],
                'shipping_street': cd['shipping_street'],
                'shipping_city': cd['shipping_city'],
                'shipping_zip_code': cd['shipping_zip_code'],
                'shipping_method_id': cd['shipping_method'].id,
                'payment_method_id': cd['payment_method'].id,
                'billing_different': cd['billing_different'],
                'billing_first_name': cd['billing_first_name'],
                'billing_last_name': cd['billing_last_name'],
                'billing_company_name': cd['billing_company_name'],
                'billing_ico': cd['billing_ico'],
                'billing_dic': cd['billing_dic'],
                'billing_street': cd['billing_street'],
                'billing_city': cd['billing_city'],
                'billing_zip_code': cd['billing_zip_code'],
            }
            request.session.modified = True
            return redirect('catalog:checkout_summary')
    else:
        form = OrderForm()

    return render(request, 'catalog/checkout.html', {'form': form})


def checkout_summary(request: HttpRequest) -> HttpResponse:
    """Display an order summary and handle order creation on POST."""
    pending_order = request.session.get('pending_order')
    if not pending_order:
        return redirect('catalog:checkout')

    cart = request.session.get('cart', {})
    items, total_qty, products_total_net, products_total_gross = calculate_cart_totals(cart)

    shipping = get_object_or_404(ShippingMethod, id=pending_order['shipping_method_id'])
    payment = get_object_or_404(PaymentMethod, id=pending_order['payment_method_id'])

    grand_total_net = products_total_net + shipping.price_net + payment.price_net
    grand_total_gross = products_total_gross + shipping.price_gross + payment.price_gross

    if request.method == 'POST':
        if not items:
            messages.error(request, 'Košík je prázdný.')
            return redirect('catalog:cart_detail')

        order_status, _ = OrderStatus.objects.get_or_create(
            code='new', defaults={'name': 'Nová'}
        )

        with transaction.atomic():
            order = Order.objects.create(
                user=None,
                status=order_status,
                shipping_method=shipping,
                payment_method=payment,
                shipping_price_net=shipping.price_net,
                shipping_vat_rate=shipping.vat_rate.rate,
                payment_price_net=payment.price_net,
                payment_price_gross=payment.price_gross,
                payment_vat_rate=payment.vat_rate.rate,
                total_price_net=grand_total_net,
                total_price_gross=grand_total_gross,
                customer_email=pending_order['customer_email'],
                customer_phone=pending_order['customer_phone'],
                shipping_first_name=pending_order['shipping_first_name'],
                shipping_last_name=pending_order['shipping_last_name'],
                shipping_street=pending_order['shipping_street'],
                shipping_city=pending_order['shipping_city'],
                shipping_zip_code=pending_order['shipping_zip_code'],
                billing_first_name=pending_order.get('billing_first_name', ''),
                billing_last_name=pending_order.get('billing_last_name', ''),
                billing_company_name=pending_order.get('billing_company_name', ''),
                billing_ico=pending_order.get('billing_ico', ''),
                billing_dic=pending_order.get('billing_dic', ''),
                billing_street=pending_order.get('billing_street', ''),
                billing_city=pending_order.get('billing_city', ''),
                billing_zip_code=pending_order.get('billing_zip_code', ''),
            )

            for item in items:
                OrderItem.objects.create(
                    order=order,
                    product=item['product'],
                    quantity=item['quantity'],
                    unit_price_net=item['product'].price_net,
                    unit_price_gross=item['product'].price_gross,
                    vat_rate=item['product'].vat_rate.rate,
                )

        request.session.pop('cart', None)
        request.session.pop('pending_order', None)
        request.session.modified = True

        messages.success(request, 'Objednávka byla úspěšně vytvořena!')
        return redirect('catalog:order_success', order_id=order.id)

    return render(request, 'catalog/checkout_summary.html', {
        'pending_order': pending_order,
        'items': items,
        'products_total_net': products_total_net,
        'products_total_gross': products_total_gross,
        'shipping': shipping,
        'payment': payment,
        'grand_total_net': grand_total_net,
        'grand_total_gross': grand_total_gross,
    })


def order_success(request: HttpRequest, order_id: int) -> HttpResponse:
    """Display the thank-you page after a successful order."""
    order = get_object_or_404(Order, id=order_id)
    return render(request, 'catalog/order_success.html', {'order': order})
