"""
Thin wrapper around the official `razorpay` Python SDK.
Keeping this in one file means the rest of the app never touches the SDK
directly — handy if Razorpay's API ever changes shape.
"""

import razorpay

from config import Config

_client = None


def get_client():
    global _client
    if _client is None:
        _client = razorpay.Client(auth=(Config.RAZORPAY_KEY_ID, Config.RAZORPAY_KEY_SECRET))
    return _client


def create_payment_link(order_id, buyer_phone, amount_paise, description):
    """
    Creates a Razorpay Payment Link and returns (link_id, short_url).
    `amount_paise` must be an integer number of paise (₹1 = 100 paise).
    """
    client = get_client()
    payload = {
        "amount": amount_paise,
        "currency": "INR",
        "description": description,
        "customer": {"contact": buyer_phone},
        "notify": {"sms": True, "whatsapp": False, "email": False},
        "reminder_enable": True,
        "notes": {"order_id": str(order_id)},
        "callback_url": f"{Config.PUBLIC_BASE_URL}/payment-complete?order_id={order_id}",
        "callback_method": "get",
    }
    link = client.payment_link.create(payload)
    return link["id"], link["short_url"]


def verify_webhook_signature(request_body: bytes, signature_header: str) -> bool:
    """
    Verifies the X-Razorpay-Signature header against the raw request body
    using the webhook secret configured in the Razorpay dashboard.
    Returns True if valid, False otherwise. Never raises.
    """
    if not Config.RAZORPAY_WEBHOOK_SECRET:
        # No secret configured (e.g. local demo without real webhooks) —
        # refuse to trust unsigned payloads in anything but explicit dev mode.
        return False
    try:
        client = get_client()
        client.utility.verify_webhook_signature(
            request_body.decode("utf-8"), signature_header, Config.RAZORPAY_WEBHOOK_SECRET
        )
        return True
    except razorpay.errors.SignatureVerificationError:
        return False
    except Exception:
        return False
