from decimal import Decimal
from typing import Dict, List, Tuple, Any

from .models import Product


# ===================== CART UTILITIES =====================
def calculate_cart_totals(cart: Dict[str, Any]) -> Tuple[List[Dict[str, Any]], int, Decimal, Decimal]:
    """
    Compute detailed cart information from session cart dictionary.

    Args:
        cart: Mapping of product ID strings to either:
              - a dict {'quantity': int, 'overstock_confirmed': bool} (new format), or
              - a plain int (legacy format, treated as overstock_confirmed=False).

    Returns:
        A tuple containing:
            - list of item dicts (product, quantity, subtotal_net, subtotal_gross, overstock_confirmed)
            - total quantity across all items
            - total net price
            - total gross price
    """
    product_ids = [int(pid) for pid in cart.keys() if pid.isdigit()]
    products = Product.objects.filter(id__in=product_ids, is_active=True)
    products_dict = {p.id: p for p in products}

    items = []
    total_quantity = 0
    total_net = Decimal('0.00')
    total_gross = Decimal('0.00')

    for product_id_str, entry in cart.items():
        if not product_id_str.isdigit():
            continue
        product_id = int(product_id_str)
        product = products_dict.get(product_id)
        if product is None:
            continue

        # Support both the new dict format and the legacy plain-int format
        if isinstance(entry, dict):
            quantity = entry.get('quantity', 1)
            overstock_confirmed = bool(entry.get('overstock_confirmed', False))
        else:
            quantity = entry
            overstock_confirmed = False

        qty = int(quantity) if isinstance(quantity, int) else 1
        if qty < 1:
            qty = 1

        item_net = product.price_net * qty
        item_gross = product.price_gross * qty

        items.append({
            'product': product,
            'quantity': qty,
            'subtotal_net': item_net,
            'subtotal_gross': item_gross,
            'overstock_confirmed': overstock_confirmed,
        })

        total_quantity += qty
        total_net += item_net
        total_gross += item_gross

    return items, total_quantity, total_net, total_gross
