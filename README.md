# Payment Recovery Concierge

**Track 3: AI Revenue Recovery — Razorpay Hackathon**

An AI agent that watches Razorpay payment links in real time, figures out
why a payment failed, and automatically takes the next best action — nudging
the buyer, switching them to an easier payment method, or offering a small
time-boxed discount — to recover a sale that would otherwise be silently lost.

## The problem

Small sellers running their shop over WhatsApp send a payment link and hope
for the best. A declined card, a UPI timeout, or a distracted buyer, and the
sale just disappears — the seller usually doesn't even notice. There's no
follow-up, because there's no one watching.

## How it works

```
Seller (WhatsApp)                Buyer (WhatsApp)
     |  "/order +91... 500 cake"       |
     v                                  |
 [Flask app] --create link--> [Razorpay] |
     |                                  |
     |---------- payment link --------->|
     |                                  |
     |          <-- buyer's card fails--|
     |                                  |
 [Razorpay webhook: payment.failed]     |
     |                                  |
 [Agent decides next move]              |
     |---- "try UPI instead" nudge ---->|
     |                                  |
     |          <----- buyer pays ------|
     |                                  |
 [Razorpay webhook: payment_link.paid]  |
     |                                  |
 [Dashboard: +₹500 recovered]           |
```

The agent's decision-making (`agent.py`) is a **pure, unit-tested function**
that escalates through a ladder on each failure:

1. **1st failure** → suggest switching to UPI
2. **2nd failure** → plain reminder
3. **3rd failure** → fresh payment link with a small discount (configurable, default 10%)
4. **Still unpaid** → give up, notify the seller to follow up personally

If `ANTHROPIC_API_KEY` is set, Claude rewrites each nudge to sound natural
instead of templated (`ai_copywriter.py`). If it's not set, the app falls
back to solid hand-written templates — the demo never breaks for lack of a key.

## Project structure

```
app.py               Flask routes, webhooks, dashboard
agent.py             The decision-making core (pure function + tests)
ai_copywriter.py      Optional Claude-powered message rewriting
razorpay_client.py    Razorpay Payment Links + webhook signature verification
whatsapp_client.py    Twilio WhatsApp sandbox messaging
models.py             SQLite data layer (orders + recovery stats)
config.py             Environment variable loading
templates/dashboard.html   Live-updating recovery dashboard
static/style.css      Dashboard styling
tests/test_agent.py    Unit tests for the agent's decision logic
```

## Setup

### 1. Install dependencies

```bash
python -m venv venv
source venv/bin/activate   # Windows: venv\Scripts\activate
pip install -r requirements.txt
```

### 2. Razorpay (test mode)

1. Sign up at [dashboard.razorpay.com](https://dashboard.razorpay.com) and switch to **Test Mode**.
2. Go to **Settings → API Keys** → generate a key pair → copy into `.env` as `RAZORPAY_KEY_ID` / `RAZORPAY_KEY_SECRET`.
3. Go to **Settings → Webhooks** → add webhook URL `https://<your-ngrok-url>/webhooks/razorpay`, subscribe to `payment_link.paid` and `payment.failed`, copy the webhook secret into `.env`.
4. Use Razorpay's official test card/UPI numbers (see their [test mode docs](https://razorpay.com/docs/payments/payments/test-mode/)) to simulate both successful and failed payments during your demo.

### 3. Twilio WhatsApp sandbox

1. Sign up at [twilio.com](https://www.twilio.com), go to **Messaging → Try it out → Send a WhatsApp message**.
2. Copy your **Account SID** and **Auth Token** into `.env`.
3. **Important sandbox rule:** both the seller's phone and the buyer's phone must send the shown `join <code>` message to the Twilio sandbox number once, or Twilio will silently refuse to deliver messages to them. Do this before rehearsing your demo.
4. In the Twilio console, set the sandbox's "when a message comes in" webhook to `https://<your-ngrok-url>/webhooks/whatsapp`.

### 4. Expose your local server (for webhooks to reach you)

```bash
ngrok http 5000
```

Copy the `https://xxxx.ngrok-free.app` URL into `PUBLIC_BASE_URL` in `.env`, and use it for both webhook URLs above.

### 5. Run it

```bash
cp .env.example .env   # then fill in your real values
python app.py
```

Open `http://localhost:5000` for the dashboard.

## Running the tests

```bash
python -m unittest tests.test_agent -v
```

## Demo script (for your pitch video)

1. From the seller's WhatsApp: send `/order +91<buyer_number> 500 chocolate cake order`.
2. Buyer receives the payment link, opens Razorpay checkout, **uses a test card
   number that simulates a decline**.
3. Within seconds, the buyer gets a WhatsApp nudge suggesting UPI instead — no
   human touched anything.
4. Buyer completes payment via UPI (test mode).
5. Dashboard updates live: **"₹500 recovered."**

If you'd rather rehearse offline without real webhooks, use the simulate
endpoints once you've created a test order:

```bash
curl -X POST http://localhost:5000/api/simulate/1/fail
curl -X POST http://localhost:5000/api/simulate/1/pay
```

## Notes / honest limitations

- The escalation ladder is currently attempt-count based, not time-delay
  based — `NUDGE_DELAY_SECONDS` in `config.py` is a hook for adding real
  waiting periods between nudges if you want to extend this.
- Discount amounts and the number of escalation steps are intentionally
  simple and easy to explain on stage — they're also easy to make
  configurable per-seller as a next step.
- This uses Twilio's shared WhatsApp **sandbox** number, which is fine for a
  hackathon demo but requires a Twilio-approved sender for production use.
