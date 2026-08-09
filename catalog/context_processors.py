from typing import Dict, Any
from django.http import HttpRequest


# ===================== CART CONTEXT PROCESSORS =====================
def cart(request: HttpRequest) -> Dict[str, Any]:
    """Expose total cart item count to all templates globally."""
    cart_data: Dict[str, Any] = request.session.get('cart', {})

    total_quantity = 0
    for key, entry in cart_data.items():
        if not key.isdigit():
            continue
        if isinstance(entry, dict):
            qty = entry.get('quantity', 0)
        else:
            qty = entry
        if isinstance(qty, int):
            total_quantity += qty

    return {
        'cart_total_quantity': total_quantity
    }
