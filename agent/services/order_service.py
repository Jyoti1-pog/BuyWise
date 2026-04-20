"""
Order service — creates mock orders.
No real payment processing; generates a structured Order DB record.
"""
from __future__ import annotations
import random
import string
from datetime import datetime

from agent.models import Order, OrderItem, ProductCard, Session
from agent.catalog import MOCK_USER_PROFILE


def _generate_order_ref() -> str:
    """Generate a human-readable order reference like BW-20260421-A3F7."""
    date_str = datetime.now().strftime("%Y%m%d")
    suffix = "".join(random.choices(string.ascii_uppercase + string.digits, k=4))
    return f"BW-{date_str}-{suffix}"


def place_mock_order(
    session: Session,
    product: ProductCard,
    guest_id: str = "",
) -> Order:
    """
    Create a confirmed mock order for the given ProductCard.
    Uses MOCK_USER_PROFILE for shipping address + payment.
    """
    profile = MOCK_USER_PROFILE
    shipping_address = (
        f"{profile['full_name']}\n"
        f"{profile['address_line1']}\n"
        f"{profile.get('address_line2', '')}\n"
        f"{profile['city']} - {profile['pincode']}\n"
        f"Phone: {profile['phone']}"
    ).strip()

    payment_display = (
        f"{profile['default_payment']} ending ••••{profile['card_last4']}"
        if profile["default_payment"] == "card"
        else profile["default_payment"]
    )

    # Random realistic delivery estimate
    estimated_days = random.randint(3, 7)

    order = Order.objects.create(
        session=session,
        guest_id=guest_id,
        order_ref=_generate_order_ref(),
        status="confirmed",
        total_amount=product.price,
        currency=product.currency,
        payment_method=payment_display,
        shipping_address=shipping_address,
        estimated_delivery_days=estimated_days,
    )

    OrderItem.objects.create(
        order=order,
        product=product,
        product_name=product.name,
        unit_price=product.price,
        quantity=1,
        subtotal=product.price,
    )

    # Update session state
    session.state = "ordered"
    session.save(update_fields=["state", "updated_at"])

    return order
