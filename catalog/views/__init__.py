from .accounts import profile_update, register
from .cart import add_to_cart, cart_detail, cart_remove
from .catalog import category_detail, homepage, product_detail, product_list
from .orders import (
    checkout,
    checkout_summary,
    order_detail,
    order_history,
    order_invoice_download,
    order_success,
)
from .products_admin import product_create, product_delete, product_update
from .quotes import custom_quote

__all__ = [
    'add_to_cart',
    'cart_detail',
    'cart_remove',
    'category_detail',
    'checkout',
    'checkout_summary',
    'custom_quote',
    'homepage',
    'order_detail',
    'order_history',
    'order_invoice_download',
    'order_success',
    'product_create',
    'product_delete',
    'product_detail',
    'product_list',
    'product_update',
    'profile_update',
    'register',
]
