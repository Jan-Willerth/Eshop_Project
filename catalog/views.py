from decimal import Decimal

from django.contrib import messages
from django.contrib.auth import login as auth_login
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.db.models import F
from django.http import HttpRequest, HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils.safestring import mark_safe
from django.views.decorators.http import require_POST

from .cart_utils import calculate_cart_totals, cart_has_unconfirmed_overstock
from .forms import (
    CartAddProductForm,
    OrderForm,
    ProfileUpdateForm,
    QuoteRequestForm,
    RegistrationForm,
)
from .models import (
    Category,
    CompanyBillingProfile,
    Order,
    OrderItem,
    OrderStatus,
    PaymentMethod,
    Product,
    Profile,
    ShippingMethod,
    generate_invoice_pdf,
)


# ===================== CATALOG VIEWS =====================
def product_list(request: HttpRequest) -> HttpResponse:
    """Render the active product catalog with optimized category
    prefetching.
    """
    products = (
        Product.objects.filter(is_active=True)
        .select_related('vat_rate', 'category__parent')
    )
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
        is_active=True,
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
            initial['product'] = get_object_or_404(
                Product, id=product_id, is_active=True
            )
        if quantity:
            initial['quantity'] = quantity

    if request.method == 'POST':
        form = QuoteRequestForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(
                request,
                'Vaše poptávka byla odeslána. Budeme vás kontaktovat.',
            )
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
            existing_qty = (
                existing_entry.get('quantity', 0)
                if isinstance(existing_entry, dict)
                else existing_entry
            )
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
            stock_warning = (
                "Zboží není skladem. Předpokládaná dodací lhůta 3–5 pracovních dnů."
            )
        elif is_overstock:
            stock_warning = (
                f"Požadované množství ({new_quantity}) přesahuje skladové zásoby "
                f"({product.stock}). Dodací lhůta může být prodloužena."
            )

        if request.headers.get('x-requested-with') == 'XMLHttpRequest':
            item_subtotal_net = (
                product.price_net * new_quantity
                if new_quantity > 0
                else Decimal('0.00')
            )
            item_subtotal_gross = (
                product.price_gross * new_quantity
                if new_quantity > 0
                else Decimal('0.00')
            )

            return JsonResponse({
                'success': True,
                'message': f'Produkt "{product.name}" byl přidán do košíku.',
                'product_name': product.name,
                'cart_total_quantity': total_qty,
                'total_gross': f"{total_gross:.2f}",
                'total_net': f"{total_net:.2f}",
                'item_subtotal': f"{item_subtotal_gross:.2f}",
                'item_subtotal_net': f"{item_subtotal_net:.2f}",
                'item_subtotal_gross': f"{item_subtotal_gross:.2f}",
                'item_quantity': new_quantity,
                'stock_warning': stock_warning,
                'is_overstock': is_overstock,
                'overstock_confirmed': overstock_confirmed,
                'stock': product.stock,
            })

        messages.success(
            request,
            f'Produkt "{product.name}" byl přidán do košíku.',
        )
        return redirect('catalog:cart_detail')

    raw_quantity = request.POST.get('quantity', '1')
    quote_url = (
        reverse('catalog:custom_quote')
        + f'?product={product.id}&quantity={raw_quantity}'
    )

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
    _, _, _, products_total_gross = calculate_cart_totals(cart)
    form_context = {
        'products_total_gross': products_total_gross,
        'is_registered': request.user.is_authenticated,
    }

    if cart_has_unconfirmed_overstock(cart):
        messages.error(
            request,
            'V košíku máte položky přesahující skladové zásoby. '
            'Pro pokračování je nutné potvrdit souhlas s delší dodací lhůtou.',
        )
        return redirect('catalog:cart_detail')

    if request.method == 'POST':
        form = OrderForm(request.POST, **form_context)
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
                'customer_street': cd['customer_street'],
                'customer_city': cd['customer_city'],
                'customer_zip_code': cd['customer_zip_code'],
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
                'delivery_different': cd['delivery_different'],
                'delivery_street': cd['delivery_street'],
                'delivery_city': cd['delivery_city'],
                'delivery_zip_code': cd['delivery_zip_code'],
            }
            request.session.modified = True
            return redirect('catalog:checkout_summary')
    else:
        initial = {}
        if request.user.is_authenticated:
            profile = getattr(request.user, 'profile', None)
            if profile:
                initial = {
                    'customer_email': request.user.email,
                    'customer_phone': profile.phone,
                    'shipping_first_name': request.user.first_name,
                    'shipping_last_name': request.user.last_name,
                    'shipping_street': profile.street,
                    'shipping_city': profile.city,
                    'shipping_zip_code': profile.zip_code,
                }
                company_billing = getattr(profile, 'company_billing', None)
                if company_billing:
                    initial.update({
                        'billing_different': True,
                        'billing_first_name': company_billing.contact_first_name,
                        'billing_last_name': company_billing.contact_last_name,
                        'billing_company_name': company_billing.company_name,
                        'billing_ico': company_billing.ico,
                        'billing_dic': company_billing.dic,
                        'billing_street': company_billing.street,
                        'billing_city': company_billing.city,
                        'billing_zip_code': company_billing.zip_code,
                    })
        form = OrderForm(initial=initial, **form_context)

    payment_limit = (
        Decimal('5000.00')
        if request.user.is_authenticated
        else Decimal('1000.00')
    )
    return render(request, 'catalog/checkout.html', {
        'form': form,
        'payment_limit': payment_limit,
    })


def checkout_summary(request: HttpRequest) -> HttpResponse:
    """Display an order summary and handle order creation on POST."""
    pending_order = request.session.get('pending_order')
    if not pending_order:
        return redirect('catalog:checkout')

    cart = request.session.get('cart', {})
    items, total_qty, products_total_net, products_total_gross = (
        calculate_cart_totals(cart)
    )

    shipping = get_object_or_404(
        ShippingMethod, id=pending_order['shipping_method_id']
    )
    payment = get_object_or_404(
        PaymentMethod, id=pending_order['payment_method_id']
    )

    grand_total_net = products_total_net + shipping.price_net + payment.price_net
    grand_total_gross = (
        products_total_gross + shipping.price_gross + payment.price_gross
    )

    if request.method == 'POST':
        if not items:
            messages.error(request, 'Košík je prázdný.')
            return redirect('catalog:cart_detail')

        order_status, _ = OrderStatus.objects.get_or_create(
            code='new', defaults={'name': 'Nová'}
        )

        with transaction.atomic():
            order = Order.objects.create(
                user=request.user if request.user.is_authenticated else None,
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
                Product.objects.filter(pk=item['product'].pk).update(
                    stock=F('stock') - item['quantity']
                )

        request.session.pop('cart', None)
        request.session.pop('pending_order', None)
        request.session['last_order_id'] = order.id
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
    """Display the thank-you page only to its owner or the just-completed
    anonymous checkout.
    """
    if request.user.is_authenticated:
        order = get_object_or_404(Order, id=order_id, user=request.user)
    else:
        if request.session.get('last_order_id') != order_id:
            return redirect('catalog:login')
        order = get_object_or_404(Order, id=order_id, user__isnull=True)
    return render(request, 'catalog/order_success.html', {'order': order})


@login_required(login_url='catalog:login')
def order_detail(request: HttpRequest, order_id: int) -> HttpResponse:
    """Show a complete order detail to its authenticated owner only."""
    order = get_object_or_404(
        Order.objects.select_related(
            'status', 'shipping_method', 'payment_method'
        ).prefetch_related('items__product'),
        id=order_id,
        user=request.user,
    )
    order_items = [
        {
            'item': item,
            'total_net': item.unit_price_net * item.quantity,
            'total_gross': item.unit_price_gross * item.quantity,
        }
        for item in order.items.all()
    ]
    shipping_gross = order.shipping_price_net * (
        1 + order.shipping_vat_rate / Decimal('100')
    )

    return render(request, 'catalog/order_detail.html', {
        'order': order,
        'order_items': order_items,
        'shipping_gross': shipping_gross,
    })


@login_required(login_url='catalog:login')
def order_invoice_download(request: HttpRequest, order_id: int) -> HttpResponse:
    """Download a tax document PDF only for the authenticated order owner."""
    order = get_object_or_404(
        Order.objects.prefetch_related('items__product').select_related(
            'shipping_method', 'payment_method'
        ),
        id=order_id,
        user=request.user,
    )
    is_business = bool(order.billing_company_name)
    filename_prefix = (
        'danovy_doklad' if is_business else 'zjednoduseny_danovy_doklad'
    )
    response = HttpResponse(
        generate_invoice_pdf(order),
        content_type='application/pdf',
    )
    response['Content-Disposition'] = (
        f'attachment; filename="{filename_prefix}_{order.id}.pdf"'
    )
    return response


# ===================== AUTH VIEWS =====================
def register(request: HttpRequest) -> HttpResponse:
    """Display and process the registration form; log the user in on
    success.
    """
    if request.method == 'POST':
        form = RegistrationForm(request.POST)
        if form.is_valid():
            user = form.save()
            auth_login(request, user)
            messages.success(
                request,
                'Registrace proběhla úspěšně, jste přihlášeni.',
            )
            return redirect('catalog:product_list')
    else:
        form = RegistrationForm()

    return render(request, 'catalog/register.html', {'form': form})


@login_required(login_url='catalog:login')
def profile_update(request: HttpRequest) -> HttpResponse:
    """Allow a signed-in customer to maintain their saved checkout details."""
    profile, _ = Profile.objects.get_or_create(user=request.user)
    company_billing = getattr(profile, 'company_billing', None)

    if request.method == 'POST':
        form = ProfileUpdateForm(request.POST, user=request.user)
        if form.is_valid():
            data = form.cleaned_data
            with transaction.atomic():
                request.user.email = data['email']
                request.user.first_name = data['first_name']
                request.user.last_name = data['last_name']
                request.user.save(update_fields=['first_name', 'last_name', 'email'])

                profile.phone = data['phone']
                profile.street = data['street']
                profile.city = data['city']
                profile.zip_code = data['zip_code']
                profile.save()

                if data['billing_different']:
                    CompanyBillingProfile.objects.update_or_create(
                        profile=profile,
                        defaults={
                            'contact_first_name': data['billing_first_name'],
                            'contact_last_name': data['billing_last_name'],
                            'company_name': data['billing_company_name'],
                            'ico': data['billing_ico'],
                            'dic': data['billing_dic'],
                            'street': data['billing_street'],
                            'city': data['billing_city'],
                            'zip_code': data['billing_zip_code'],
                        },
                    )
                elif company_billing:
                    company_billing.delete()

            messages.success(request, 'Profil byl úspěšně aktualizován.')
            return redirect('catalog:profile_update')
    else:
        initial = {
            'email': request.user.email,
            'first_name': request.user.first_name,
            'last_name': request.user.last_name,
            'phone': profile.phone,
            'street': profile.street,
            'city': profile.city,
            'zip_code': profile.zip_code,
        }
        if company_billing:
            initial.update({
                'billing_different': True,
                'billing_first_name': company_billing.contact_first_name,
                'billing_last_name': company_billing.contact_last_name,
                'billing_company_name': company_billing.company_name,
                'billing_ico': company_billing.ico,
                'billing_dic': company_billing.dic,
                'billing_street': company_billing.street,
                'billing_city': company_billing.city,
                'billing_zip_code': company_billing.zip_code,
            })
        form = ProfileUpdateForm(initial=initial, user=request.user)

    return render(request, 'catalog/profile_update.html', {'form': form})


@login_required(login_url='catalog:login')
def order_history(request: HttpRequest) -> HttpResponse:
    """Display the logged-in user's own order history."""
    orders = Order.objects.filter(user=request.user).order_by('-created_at')
    return render(request, 'catalog/order_history.html', {'orders': orders})
