# Emulator

Start the local Stripe-like emulator:

```bash
python app.py
```

Default address: `http://127.0.0.1:8000`

## Current Phase 0 Endpoints

- `GET /health`
- `GET /v1/payment_intents`
- `GET /v1/payment_intents/{id}`
- `POST /v1/payment_intents`
- `POST /v1/payment_intents/{id}/confirm`
- `POST /v1/payment_intents/{id}/cancel`
- `POST /v1/payment_intents/{id}/capture`
- `POST /v1/refunds`

This is a scaffold to support the first-phase test harness and will be expanded in later phases.
