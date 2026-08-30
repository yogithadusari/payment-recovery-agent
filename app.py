"""
Payment Recovery Concierge — main Flask app.
 
Routes:
  GET  /                        Dashboard (human-facing)
  GET  /api/stats               JSON summary stats for the dashboard
  GET  /api/orders              JSON list of recent orders
  POST /webhooks/whatsapp       Twilio inbound WhatsApp messages (seller commands)
  POST /webhooks/razorpay       Razorpay payment events
  GET  /payment-complete        Razorpay callback landing page (buyer sees this)
  POST /api/simulate/<event>    Fire a fake webhook locally, no real Razorpay needed
 
Run with:  python app.py
"""
 
import re
 
from flask import Flask, request, jsonify, render_template, redirect
 
import agent
import models
import razorpay_client
import whatsapp_client
from config import Config
 
app = Flask(__name__)
app.config["SECRET_KEY"] = Config.SECRET_KEY
 
ORDER_COMMAND_RE = re.compile(
    r"^/order\s+(?P<phone>\+?\d{10,15})\s+(?P<amount>\d+(?:\.\d{1,2})?)\s+(?P<description>.+)$",
    re.IGNORECASE,
)
 
 
# ---------------------------------------------------------------- dashboard
 
@app.route("/")
def dashboard():
    return render_template("dashboard.html")
 
 
@app.route("/api/stats")
def api_stats():
    stats = models.get_stats()
    stats["recovered_amount_rupees"] = stats["recovered_amount_paise"] / 100
    stats["direct_amount_rupees"] = stats["direct_amount_paise"] / 100
    return jsonify(stats)
 
 
@app.route("/api/orders")
def api_orders():
    orders = models.list_orders()
    for o in orders:
        o["amount_rupees"] = (o["amount_paise"] - o["discount_paise"]) / 100
    return jsonify(orders)
 
 
# ---------------------------------------------------------------- WhatsApp inbound (seller side)
 
@app.route("/webhooks/whatsapp", methods=["POST"])
def whatsapp_webhook():
    """
    Handles inbound WhatsApp messages via Twilio. Sellers place an order with:
 
        /order +919876543210 500 2 chocolate cakes
 
    (buyer's WhatsApp number, amount in rupees, then a free-text description)
    """
    from_number = request.form.get("From", "").replace("whatsapp:", "")
    body = (request.form.get("Body") or "").strip()
 
    match = ORDER_COMMAND_RE.match(body)
    if not match:
        whatsapp_client.send_whatsapp(
            from_number,
            "Didn't understand that. Format:\n/order <buyer_number> <amount> <description>\n"
            "Example: /order +919876543210 500 2 chocolate cakes",
        )
        return ("", 204)
 
    buyer_phone = match.group("phone")
    if not buyer_phone.startswith("+"):
        buyer_phone = "+" + buyer_phone
    amount_paise = int(round(float(match.group("amount")) * 100))
    description = match.group("description")
 
    order_id = models.create_order(from_number, buyer_phone, description, amount_paise)
    link_id, short_url = razorpay_client.create_payment_link(
        order_id, buyer_phone, amount_paise, description
    )
    models.attach_payment_link(order_id, link_id, short_url)
 
    whatsapp_client.send_whatsapp(
        buyer_phone,
        f"Hi! You have a new order: \"{description}\" for ₹{amount_paise / 100:.0f}. "
        f"Pay here: {short_url}",
    )
    whatsapp_client.send_whatsapp(
        from_number, f"Order #{order_id} created and link sent to {buyer_phone}."
    )
    return ("", 204)
 
 
# ---------------------------------------------------------------- Razorpay webhook
 
@app.route("/webhooks/razorpay", methods=["POST"])
def razorpay_webhook():
    signature = request.headers.get("X-Razorpay-Signature", "")
    if not razorpay_client.verify_webhook_signature(request.get_data(), signature):
        return jsonify({"error": "invalid signature"}), 400
 
    payload = request.get_json(force=True)
    event = payload.get("event", "")
    entity = payload.get("payload", {})
 
    link_id = None
    if "payment_link" in entity:
        link_id = entity["payment_link"]["entity"]["id"]
    elif "payment" in entity:
        link_id = entity["payment"]["entity"].get("invoice_id") or None
 
    if not link_id:
        return jsonify({"status": "ignored"}), 200
 
    order = models.get_order_by_link_id(link_id)
    if not order:
        return jsonify({"status": "unknown_order"}), 200
 
    if event == "payment_link.paid":
        agent.handle_payment_paid(order["id"])
    elif event in ("payment_link.expired", "payment.failed"):
        agent.handle_payment_failed(order["id"])
 
    return jsonify({"status": "ok"}), 200
 
 
# ---------------------------------------------------------------- buyer-facing callback
 
@app.route("/payment-complete")
def payment_complete():
    order_id = request.args.get("order_id")
    return f"<h2>Thank you!</h2><p>We're confirming your payment for order #{order_id}. " \
           f"You'll get a WhatsApp confirmation shortly.</p>"
 
 
# ---------------------------------------------------------------- local demo helpers (no real webhook needed)
 
@app.route("/api/create-order", methods=["POST"])
def api_create_order():
    """
    Creates an order and a real Razorpay payment link, then messages the
    buyer over WhatsApp — all of this is OUTBOUND (this app calling Razorpay
    and Twilio), so it works from localhost with no public URL required.
    Lets you demo the whole flow without ever setting up a tunnel.
    """
    data = request.get_json(force=True)
    buyer_phone = data["buyer_phone"]
    # For a solo demo, the same person is playing both seller and buyer —
    # default the seller number to the buyer number unless one is explicitly given.
    seller_phone = data.get("seller_phone") or buyer_phone
    description = data["description"]
    amount_paise = int(round(float(data["amount"]) * 100))
 
    order_id = models.create_order(seller_phone, buyer_phone, description, amount_paise)
    link_id, short_url = razorpay_client.create_payment_link(
        order_id, buyer_phone, amount_paise, description
    )
    models.attach_payment_link(order_id, link_id, short_url)
 
    whatsapp_client.send_whatsapp(
        buyer_phone,
        f"Hi! You have a new order: \"{description}\" for ₹{amount_paise / 100:.0f}. "
        f"Pay here: {short_url}",
    )
    return jsonify(models.get_order(order_id))
 
 
@app.route("/api/simulate/<int:order_id>/<event>", methods=["POST"])
def simulate(order_id, event):
    """
    Lets you rehearse the whole demo flow locally without a public webhook URL.
    event: 'fail' or 'pay'
    """
    if event == "fail":
        agent.handle_payment_failed(order_id)
    elif event == "pay":
        agent.handle_payment_paid(order_id)
    else:
        return jsonify({"error": "event must be 'fail' or 'pay'"}), 400
    return jsonify(models.get_order(order_id))
 
 
if __name__ == "__main__":
    models.init_db()
    app.run(debug=True, port=5000)
 
