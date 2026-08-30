"""
Central configuration for the Payment Recovery Concierge.
All secrets are read from environment variables (see .env.example).
Never commit a real .env file to git.
"""

import os
from dotenv import load_dotenv

load_dotenv()


class Config:
    # --- Razorpay ---
    RAZORPAY_KEY_ID = os.getenv("RAZORPAY_KEY_ID", "")
    RAZORPAY_KEY_SECRET = os.getenv("RAZORPAY_KEY_SECRET", "")
    RAZORPAY_WEBHOOK_SECRET = os.getenv("RAZORPAY_WEBHOOK_SECRET", "")

    # --- Twilio WhatsApp sandbox ---
    TWILIO_ACCOUNT_SID = os.getenv("TWILIO_ACCOUNT_SID", "")
    TWILIO_AUTH_TOKEN = os.getenv("TWILIO_AUTH_TOKEN", "")
    # Twilio's shared WhatsApp sandbox number. Same for every developer
    # until you apply for a production WhatsApp sender.
    TWILIO_WHATSAPP_FROM = os.getenv("TWILIO_WHATSAPP_FROM", "whatsapp:+14155238886")

    # --- Optional: Anthropic API for smarter, more natural nudge messages ---
    # If this is not set, the agent falls back to solid hand-written templates,
    # so the demo never breaks for lack of an API key.
    ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")

    # --- App ---
    SECRET_KEY = os.getenv("SECRET_KEY", "dev-secret-change-me")
    DATABASE_PATH = os.getenv("DATABASE_PATH", "recovery.db")
    # Public base URL of this server once deployed / tunnelled (e.g. via ngrok).
    # Used to build the Razorpay callback_url.
    PUBLIC_BASE_URL = os.getenv("PUBLIC_BASE_URL", "http://localhost:5000")

    # --- Agent behaviour knobs ---
    MAX_DISCOUNT_PERCENT = int(os.getenv("MAX_DISCOUNT_PERCENT", "10"))
    NUDGE_DELAY_SECONDS = int(os.getenv("NUDGE_DELAY_SECONDS", "0"))  # 0 = react instantly
