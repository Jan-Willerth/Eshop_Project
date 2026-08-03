from typing import Dict, Any
from django.http import HttpRequest


# ===================== CART CONTEXT PROCESSORS =====================
def cart(request: HttpRequest) -> Dict[str, Any]:
    """Expose total cart item count to all templates globally."""
    cart_data: Dict[str, int] = request.session.get('cart', {})

    total_quantity = sum(
        qty for key, qty in cart_data.items()
        if key.isdigit() and isinstance(qty, int)
    )

    return {
        'cart_total_quantity': total_quantity
    }
