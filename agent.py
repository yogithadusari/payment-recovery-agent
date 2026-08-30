"""
The agent. This is the part of the project worth demoing.

`decide_next_action` is a PURE function (no network calls, no side effects) —
given an order's current attempt count, it decides what to do next. Keeping
it pure means it's trivially unit-testable (see tests/test_agent.py) and the
"decision" logic can be explained on a whiteboard without touching a single
API.

`handle_payment_failed` and `handle_payment_paid` are the impure shell around
it: they call the pure function, then actually talk to Razorpay/Twilio/the DB.
"""

from dataclasses import dataclass

import models
import razorpay_client
import whatsapp_client
from config import Config

try:
    from ai_copywriter import craft_message
except ImportError:
    craft_message = None


@dataclass
class Action:
    kind: str  # "nudge_upi" | "nudge_reminder" | "offer_discount" | "give_up"
    message_template: str


# Escalation ladder. Index = attempt_count BEFORE this failure.
LADDER = [
    Action(
        kind="nudge_upi",
        message_template=(
            "Hi! Looks like your payment for \"{description}\" (₹{amount}) didn't go "
            "through. Try paying via UPI instead — it's usually faster: {link}"
        ),
    ),
    Action(
        kind="nudge_reminder",
        message_template=(
            "Quick reminder — your order \"{description}\" (₹{amount}) is still "
            "waiting on payment. Here's your link again: {link}"
        ),
    ),
    Action(
        kind="offer_discount",
        message_template=(
            "We'd hate for you to miss out! Here's ₹{discount} off your order "
            "\"{description}\" — pay just ₹{amount} in the next hour: {link}"
        ),
    ),
]


def decide_next_action(attempt_count: int) -> Action | None:
    """Returns the next Action for this attempt count, or None if the agent
    should give up (order marked as lost)."""
    if attempt_count < len(LADDER):
        return LADDER[attempt_count]
    return None


def _format_message(action: Action, order: dict, link_url: str, discount_rupees: int = 0) -> str:
    rupees = (order["amount_paise"] - order.get("discount_paise", 0)) / 100
    plain = action.message_template.format(
        description=order["description"],
        amount=f"{rupees:.0f}",
        discount=discount_rupees,
        link=link_url,
    )

    if craft_message and Config.ANTHROPIC_API_KEY:
        try:
            return craft_message(action.kind, order, plain)
        except Exception:
            pass  # fall back to the template — demo must never break
    return plain


def handle_payment_failed(order_id: int):
    """Called when Razorpay reports a failed/expired/abandoned payment attempt."""
    order = models.get_order(order_id)
    if not order:
        return

    action = decide_next_action(order["attempt_count"])

    if action is None:
        models.update_status(order_id, "lost", bump_attempt=True, mark_failure=True)
        whatsapp_client.send_whatsapp(
            order["seller_phone"],
            f"Order #{order_id} (\"{order['description']}\") couldn't be recovered "
            f"after {order['attempt_count']} attempts. Might be worth a personal follow-up.",
        )
        return

    link_url = order["razorpay_short_url"]
    discount_rupees = 0

    if action.kind == "offer_discount":
        discount_pct = min(Config.MAX_DISCOUNT_PERCENT, 10)
        discount_paise = int(order["amount_paise"] * discount_pct / 100)
        new_amount_paise = order["amount_paise"] - discount_paise
        link_id, link_url = razorpay_client.create_payment_link(
            order_id, order["buyer_phone"], new_amount_paise,
            f"{order['description']} (discount applied)",
        )
        models.attach_payment_link(order_id, link_id, link_url)
        discount_rupees = discount_paise // 100
        models.update_status(
            order_id, action.kind, bump_attempt=True, mark_failure=True,
            discount_paise=discount_paise,
        )
    else:
        models.update_status(order_id, action.kind, bump_attempt=True, mark_failure=True)

    order = models.get_order(order_id)  # refresh after possible discount update
    message = _format_message(action, order, link_url, discount_rupees)
    whatsapp_client.send_whatsapp(order["buyer_phone"], message)


def handle_payment_paid(order_id: int):
    """Called when Razorpay confirms the payment link was successfully paid."""
    order = models.get_order(order_id)
    if not order:
        return

    models.update_status(order_id, "paid", paid=True)
    order = models.get_order(order_id)

    if order["had_failure"]:
        rupees = (order["amount_paise"] - order["discount_paise"]) / 100
        whatsapp_client.send_whatsapp(
            order["seller_phone"],
            f"Recovered! Order #{order_id} (\"{order['description']}\") just came "
            f"through for ₹{rupees:.0f} after {order['attempt_count']} follow-up(s).",
        )
    else:
        whatsapp_client.send_whatsapp(
            order["seller_phone"],
            f"Payment received for order #{order_id} (\"{order['description']}\").",
        )
