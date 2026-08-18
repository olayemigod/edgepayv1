# EdgePay API V1 and Connector V2

## Signed requests

Required headers:

- `X-EdgePay-Client-Id`
- `X-EdgePay-Timestamp`
- `X-EdgePay-Nonce`
- `X-EdgePay-Signature`
- `Idempotency-Key` for payment/refund creation

Canonical string:

```text
HTTP_METHOD
REQUEST_PATH
TIMESTAMP
NONCE
SHA256_REQUEST_BODY
```

Signature:

```text
hex(HMAC-SHA256(client_secret, canonical_string))
```

The timestamp must be within five minutes. A nonce is accepted once only. API Clients are Merchant- and scope-bound.

## V1 methods

- create Payment Request
- retrieve Payment Request and timeline
- initialise checkout
- verify payment server-side
- retrieve Transaction
- create Refund Request
- retrieve Refund Request

## Delivery verification

EdgePay sends:

- `X-EdgePay-Event-Id`
- `X-EdgePay-Event-Type`
- `X-EdgePay-Signature`

The signature is HMAC-SHA256 of the exact request body using the Delivery Endpoint secret. Consumers must verify the signature before processing and deduplicate by `event_id`.

## Connector V2 contract

Consumers implement `EdgePayConnectorV2.apply_payment_event(payload)` and must:

1. validate schema and event ID;
2. enforce local company/branch permissions;
3. process idempotently;
4. preserve submitted ERPNext accounting documents;
5. create or allocate accounting records only inside the consuming product;
6. return success only after durable local acceptance.

Provided contract classes:

- Generic ERPNext
- RetailEdge
- VetEdge
- EduEdge

## CoreEdge provisioning

CoreEdge may create or retrieve an EdgePay Merchant using an external tenant reference. EdgePay remains independent of CoreEdge. Provisioning creates a sandbox API Client on the `EdgeSuite Free` tier and returns a secret only when the client is first created.

## Delivery operations

Payment Events and Status Handoff Events automatically create signed Delivery records. The scheduler processes pending deliveries every five minutes with bounded exponential retry and Dead Letter status after the endpoint maximum attempts.
