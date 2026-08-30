"""
Thin wrapper around Twilio's WhatsApp sandbox.

Setup reminder (see README): both the seller's and the buyer's WhatsApp
numbers must send the sandbox "join <code>" message to Twilio's sandbox
number ONCE before this can message them. That's a Twilio sandbox rule,
not something this code can skip.
"""

from twilio.rest import Client

from config import Config

_client = None


def get_client():
    global _client
    if _client is None:
        _client = Client(Config.TWILIO_ACCOUNT_SID, Config.TWILIO_AUTH_TOKEN)
    return _client


def send_whatsapp(to_phone: str, message: str):
    """
    `to_phone` should be a plain E.164 number, e.g. +919876543210.
    Returns the Twilio message SID on success.
    """
    client = get_client()
    msg = client.messages.create(
        from_=Config.TWILIO_WHATSAPP_FROM,
        to=f"whatsapp:{to_phone}",
        body=message,
    )
    return msg.sid
