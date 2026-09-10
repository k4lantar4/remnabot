# WebSocket and webhooks for the web admin

## Overview

Two systems are implemented for real-time updates and integrations:

1. **WebSocket** — real-time updates in the web admin
2. **Webhooks** — sending events to external systems

## WebSocket

### Connection

The WebSocket endpoint is available at: `ws://your-api-host:port/ws`

An API token is required to connect (passed as a query parameter):

```javascript
const ws = new WebSocket('ws://localhost:8080/ws?token=YOUR_API_TOKEN');
// or
const ws = new WebSocket('ws://localhost:8080/ws?api_key=YOUR_API_TOKEN');
```

### Message format

#### Incoming messages (from the server)

```json
{
  "type": "connection",
  "status": "connected",
  "message": "WebSocket connection established"
}
```

```json
{
  "type": "user.created",
  "payload": {
    "user_id": 123,
    "telegram_id": 456789,
    "username": "testuser",
    "first_name": "Test",
    "last_name": "User",
    "referral_code": "refABC123",
    "referred_by_id": null
  },
  "timestamp": "2024-01-15T10:30:00"
}
```

#### Outgoing messages (from the client)

**Keepalive ping:**

```json
{
  "type": "ping"
}
```

The server replies:

```json
{
  "type": "pong"
}
```

### Supported events

- `user.created` — a new user was created
- `payment.completed` — a payment completed (balance top-up)
- `transaction.created` — a transaction was created
- `ticket.created` — a new ticket was created
- `ticket.status_changed` — ticket status changed
- `ticket.message_added` — a new message was added to a ticket (from the user or an admin)

## Webhooks

### Creating a webhook

```bash
POST /webhooks
Authorization: Bearer YOUR_API_TOKEN
Content-Type: application/json

{
  "name": "My Webhook",
  "url": "https://example.com/webhook",
  "event_type": "user.created",
  "secret": "optional-secret-for-signing",
  "description": "Webhook for new users"
}
```

### Supported event types

- `user.created` — a new user was created
- `payment.completed` — a payment completed
- `transaction.created` — a transaction was created
- `ticket.created` — a new ticket was created
- `ticket.status_changed` — ticket status changed

### Payload format

The webhook sends a POST request with a JSON payload:

```json
{
  "user_id": 123,
  "telegram_id": 456789,
  "username": "testuser",
  "first_name": "Test",
  "last_name": "User",
  "referral_code": "refABC123",
  "referred_by_id": null
}
```

### Request headers

- `Content-Type: application/json`
- `X-Webhook-Event: user.created` — event type
- `X-Webhook-Id: 1` — webhook ID
- `X-Webhook-Signature: sha256=...` — signature (if a secret is set)

### Payload signature

If a `secret` is provided when creating the webhook, the payload is signed with HMAC-SHA256:

```python
import hmac
import hashlib

signature = hmac.new(
    secret.encode('utf-8'),
    payload_json.encode('utf-8'),
    hashlib.sha256
).hexdigest()
```

Header: `X-Webhook-Signature: sha256={signature}`

### Verifying the signature (Python example)

```python
import hmac
import hashlib
import json

def verify_webhook_signature(payload: dict, signature_header: str, secret: str) -> bool:
    payload_json = json.dumps(payload, sort_keys=True)
    expected_signature = hmac.new(
        secret.encode('utf-8'),
        payload_json.encode('utf-8'),
        hashlib.sha256
    ).hexdigest()

    received_signature = signature_header.replace('sha256=', '')
    return hmac.compare_digest(expected_signature, received_signature)
```

### API endpoints

#### List webhooks

```
GET /webhooks?event_type=user.created&is_active=true&limit=50&offset=0
```

#### Get a webhook

```
GET /webhooks/{webhook_id}
```

#### Update a webhook

```
PATCH /webhooks/{webhook_id}
{
  "name": "Updated Name",
  "is_active": false
}
```

#### Delete a webhook

```
DELETE /webhooks/{webhook_id}
```

#### Webhook statistics

```
GET /webhooks/stats
```

#### Delivery history

```
GET /webhooks/{webhook_id}/deliveries?status=failed&limit=50&offset=0
```

### Delivery statuses

- `pending` — waiting to be sent
- `success` — delivered successfully (HTTP 200–299)
- `failed` — delivery error

### Retry logic

Automatic retry is not implemented in the current version, but it can be added via the `next_retry_at` field on `WebhookDelivery`.

## Event integration

Events are sent automatically when:

1. **A user is created** (`app/database/crud/user.py::create_user`)
2. **A transaction is created** (`app/database/crud/transaction.py::create_transaction`)
3. **A ticket is created** (`app/database/crud/ticket.py::create_ticket`)
4. **Ticket status changes** (`app/database/crud/ticket.py::update_ticket_status`)

## Usage examples

### JavaScript WebSocket client

```javascript
const ws = new WebSocket('ws://localhost:8080/ws?token=YOUR_TOKEN');

ws.onopen = () => {
  console.log('Connected');
};

ws.onmessage = (event) => {
  const data = JSON.parse(event.data);
  console.log('Event:', data.type, data.payload);

  if (data.type === 'user.created') {
    // Handle the new user
    updateDashboard(data.payload);
  }
};

ws.onerror = (error) => {
  console.error('WebSocket error:', error);
};

ws.onclose = () => {
  console.log('Disconnected');
};

// Keepalive ping
setInterval(() => {
  if (ws.readyState === WebSocket.OPEN) {
    ws.send(JSON.stringify({ type: 'ping' }));
  }
}, 30000);
```

### Python webhook receiver

```python
from fastapi import FastAPI, Request, HTTPException
import hmac
import hashlib
import json

app = FastAPI()
WEBHOOK_SECRET = "your-secret"

@app.post('/webhook')
async def webhook(request: Request):
    signature = request.headers.get('X-Webhook-Signature', '')
    event_type = request.headers.get('X-Webhook-Event')
    payload = await request.json()

    # Verify signature
    if not verify_signature(payload, signature, WEBHOOK_SECRET):
        raise HTTPException(status_code=401, detail='Invalid signature')

    # Handle the event
    if event_type == 'user.created':
        handle_new_user(payload)
    elif event_type == 'payment.completed':
        handle_payment(payload)

    return {'status': 'ok'}

def verify_signature(payload, signature, secret):
    payload_json = json.dumps(payload, sort_keys=True)
    expected = hmac.new(
        secret.encode(),
        payload_json.encode(),
        hashlib.sha256
    ).hexdigest()
    return hmac.compare_digest(expected, signature.replace('sha256=', ''))
```

## Security

1. **WebSocket:** requires a valid API token
2. **Webhooks:**
   - Use HTTPS for the webhook URL
   - Use a secret to sign the payload
   - Verify the signature on the receiver side
   - Restrict recipient IP addresses when possible

## Monitoring

- Check webhook statistics via `/webhooks/stats`
- Review delivery history via `/webhooks/{id}/deliveries`
- Watch logs for delivery errors
