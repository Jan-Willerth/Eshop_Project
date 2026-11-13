from decimal import Decimal

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.db.models import F
from django.http import HttpRequest, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render

from ..cart_utils import calculate_cart_totals, cart_has_unconfirmed_overstock
from ..forms import OrderForm
from ..models import (
    Order,
    OrderItem,
    OrderStatus,
    PaymentMethod,
    Product,
    ShippingMethod,
    generate_invoice_pdf,
    send_order_confirmation,
)


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
                initial['billing_different'] = profile.billing_different
                company_billing = getattr(profile, 'company_billing', None)
                if company_billing:
                    initial.update({
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
                billing_different=pending_order.get('billing_different', False),
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

            send_order_confirmation(order)

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
    is_business = order.billing_different
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


@login_required(login_url='catalog:login')
def order_history(request: HttpRequest) -> HttpResponse:
    """Display the logged-in user's own order history."""
    orders = Order.objects.filter(user=request.user).order_by('-created_at')
    return render(request, 'catalog/order_history.html', {'orders': orders})
