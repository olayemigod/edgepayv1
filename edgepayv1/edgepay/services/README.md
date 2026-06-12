# EdgePay Provider Adapter Service Layer

This directory implements the provider orchestration layer pattern for EdgePay.

## 1. Provider Adapter Pattern
To prevent vendor lock-in and make the core DocType controllers highly maintainable, payment provider integrations are decoupled from standard Frappe controllers.
Instead of writing Monnify, Paystack, or Flutterwave specific logic inside `EdgePay Payment Request` or `EdgePay Payment Transaction` document controller code:
- We define a common abstract class `BaseProvider` (`base.py`) which acts as the generic interface contract.
- Each integration inherits from `BaseProvider` (e.g. `MonnifyProvider` inside `monnify.py`).
- The `get_provider_instance` helper in the registry (`registry.py`) instantiates and returns the correct configured adapter at runtime.

## 2. Decoupling Logic
This pattern allows the DocTypes to call generic, abstract methods:
- To generate a payment url, the controller calls: `provider.build_checkout_payload(doc)` and redirects the client.
- To verify a transaction, the background worker calls: `provider.parse_verification_response(response)`.
- To validate incoming webhook signatures: `provider.verify_webhook_signature(payload, headers)`.

## 3. Adding Future Providers
To add a new payment gateway (e.g., Paystack):
1. Create a new subclass file `paystack.py` under `services/providers/` inheriting from `BaseProvider`.
2. Implement the abstract payload builders, response parsers, signature checkers, and status normalizations.
3. Import and map it in the registry `_PROVIDER_MAP` inside `registry.py` under key `"paystack"`.
4. Configure an `EdgePay Provider` document in the Frappe Desk with `provider_code = "paystack"`.
