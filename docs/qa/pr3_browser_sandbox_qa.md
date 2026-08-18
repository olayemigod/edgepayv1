# EdgePay PR #3 Browser and Monnify Sandbox QA

This runbook is the manual/external release gate for PR #3 after automated consolidation CI is green.

## Scope

Validate the consolidated EdgePay product surface and payment lifecycle without changing accounting documents or weakening merchant isolation.

Run browser QA against the PR #3 branch first with the current authoritative EdgeSuite UI `main`. Run the combined EdgeSuite theme/navigation pass separately against EdgeSuite UI PR #18 only after that PR is locally accepted.

## Preconditions

- EdgePay branch: `integration/edgepay-current-consolidation-2026-08`
- EdgePay automated CI and linters green
- Frappe v16 local test site
- `edgesuite_ui` installed before `edgepayv1`
- test browser with desktop and mobile/responsive modes
- at least two isolated EdgePay Merchants
- separate users for Admin, Manager, User, and Auditor role scenarios where those roles are configured
- Monnify sandbox Provider Account credentials for the sandbox section only
- external HTTP calls enabled only for the controlled Monnify sandbox session

Do not use production provider credentials for this gate.

## A. Local branch preparation

From the bench, update the existing local clones rather than creating a second app copy.

```bash
cd ~/frappe-bench/apps/edgepayv1
git fetch origin
git checkout integration/edgepay-current-consolidation-2026-08
git pull --ff-only origin integration/edgepay-current-consolidation-2026-08

cd ~/frappe-bench/apps/edgesuite_ui
git fetch origin
git checkout main
git pull --ff-only origin main

cd ~/frappe-bench
bench --site <site> migrate
bench build --app edgesuite_ui
bench build --app edgepayv1
bench --site <site> clear-cache
bench --site <site> clear-website-cache
```

Record the exact EdgePay and EdgeSuite UI commit SHAs used for QA.

## B. Smoke and navigation QA

Log in as an EdgePay Admin and verify:

1. EdgePay appears in the Product App selector/launcher.
2. The EdgePay waffle/product menu opens without console errors.
3. `/app/edgepay-home` loads without a manual console script or reload workaround.
4. Merchant Onboarding opens from the product navigation.
5. Payment Requests, Payment Attempts, Payment Events, Refunds, Settlements, Disputes, Chargebacks, API Clients and Delivery Endpoints open where the current role permits them.
6. Browser back/forward navigation preserves correct active menu state.
7. Direct URL navigation to an allowed EdgePay page works after refresh.
8. No EdgePay page requires CoreEdge to render.

Capture any broken route, blank page, missing bundle, console exception or permission leak with the URL and active role.

## C. Role visibility QA

Run the same navigation pass with Admin, Manager, User and Auditor test users.

For each role record:

- visible menu sections;
- allowed read actions;
- allowed create/update actions;
- blocked actions;
- whether Provider Accounts are visible;
- whether API Clients or Delivery Endpoints are visible;
- whether any blocked page can still be opened by direct URL.

Expected safety rules:

- Provider Accounts are Admin-only on the normal product surface.
- permission denial must be server-enforced, not merely hidden in the menu.
- normal users must not gain access by guessing a document URL.

## D. Merchant-isolation QA

Create or use two test merchants, Merchant A and Merchant B, with separate merchant users.

As Merchant A user:

1. Home counts and summaries contain only Merchant A data.
2. Payment Request lists contain only Merchant A records.
3. Attempts, Events, Refunds, Settlements, Disputes and Chargebacks do not expose Merchant B records.
4. Direct URL access to a known Merchant B Payment Request is denied.
5. API/status methods called from the logged-in session cannot retrieve Merchant B records.

Repeat from Merchant B in the opposite direction.

Any cross-merchant visibility is a merge blocker.

## E. Secret and sensitive-data exposure QA

Inspect normal Desk pages, browser Network responses and rendered page source where relevant.

The following must not be exposed on normal product surfaces:

- Provider API keys
- Provider secret keys
- contract codes where treated as provider credentials
- webhook tokens/secrets
- API Client secrets
- checkout tokens
- raw provider payloads containing secrets
- Authorization headers or bearer tokens

Presence-only readiness flags are acceptable where intentionally designed; secret values are not.

## F. Responsive/mobile QA

Using a real mobile browser or responsive browser mode, verify at minimum:

- EdgePay Home
- product selector/waffle
- product navigation drawer
- Merchant Onboarding
- Payment Request list and form
- Payment Attempt/Event list
- one dialog/action flow

Check for horizontal overflow, inaccessible actions, clipped dialogs, unreadable tables, broken drawers and excessive payload/reload behaviour.

## G. Monnify sandbox controlled lifecycle

Only start this section when sandbox credentials are available.

### G1. Readiness

- Provider is Monnify and enabled.
- Merchant Provider Account is Sandbox, enabled and Active.
- sandbox API key, secret key and contract code are configured on the Merchant Provider Account.
- EdgePay external HTTP calls are enabled only for this controlled session.
- webhook URL points to the EdgePay provider webhook endpoint for Monnify.
- provider webhook signature validation is active.

### G2. Checkout initiation

Create a fresh Payment Request with a unique reference and initialize checkout.

Record:

- Payment Request name/reference
- Payment Attempt name/number
- provider payment reference
- checkout URL
- amount/currency
- timestamp

Expected:

- request becomes `Initiated`;
- attempt becomes `Initiated`;
- provider reference is registered;
- a repeated initialization reuses the active checkout attempt rather than creating an unnecessary duplicate.

### G3. Successful sandbox payment

Complete the Monnify sandbox payment using the provider checkout flow.

Verify that the authoritative provider result reaches EdgePay through signed webhook and/or explicit verification.

Expected final truth:

- transaction = `Success`;
- attempt = `Successful`;
- request = `Paid` for full payment;
- paid/outstanding totals reconcile to the Payment Request amount;
- Payment Event history records the lifecycle;
- source handoff/delivery is queued or completed according to the configured consumer;
- no submitted ERPNext accounting document is mutated by EdgePay.

### G4. Duplicate webhook

Replay the exact same signed sandbox webhook event when possible, or reproduce the same event reference in a controlled test harness.

Expected:

- event is treated idempotently;
- no duplicate transaction is created;
- no duplicate payment total is counted;
- existing successful state remains unchanged.

### G5. Stale status regression

After a successful transaction, send or simulate a later stale `PENDING` or `FAILED` provider event for the same transaction reference.

Expected:

- successful Transaction remains `Success`;
- successful attempt is not downgraded;
- Payment Request remains paid according to payment totals;
- stale event may be logged, but it must not reverse authoritative successful payment truth.

### G6. Failed attempt and retry

Create a separate Payment Request and force/obtain a failed sandbox attempt.

Expected:

- failed attempt = `Failed`;
- unpaid request = `Failed`;
- initializing checkout again creates a new attempt;
- request returns to `Initiated`;
- previous failed attempt/event history remains immutable;
- successful retry subsequently pays the same Payment Request without overwriting prior attempt history.

### G7. Invalid webhook signature

Send a controlled webhook payload with an invalid signature.

Expected:

- event processing fails safely;
- Payment Request and Transaction truth do not mutate;
- no secret values are written to user-visible errors;
- endpoint remains usable by Monnify as an unauthenticated HTTP endpoint but accepts state changes only after signature validation.

## H. EdgeSuite UI PR #18 combined visual pass

Do this only after the baseline EdgePay pass above succeeds and EdgeSuite UI PR #18 has been locally visually accepted.

Switch the local EdgeSuite UI clone to `agent/edgeui-theme-foundation`, rebuild `edgesuite_ui` and `edgepayv1`, clear caches, then repeat the visual portions of sections B and F.

Additionally verify:

- Light, Dark, Auto and System modes;
- approved palette switching;
- avatar theme controls;
- desktop expanded navigation;
- collapsed icon rail;
- section expansion from the rail;
- remembered navigation state;
- mobile drawer behaviour;
- EdgePay pages inherit EdgeSuite semantic tokens without product-specific chrome conflicts.

Do not merge EdgePay solely because the shared theme branch looks correct; both repositories retain their own release gates.

## I. Pass/fail record

For every failed scenario record:

- section/scenario ID;
- user/role;
- merchant;
- browser/device;
- exact URL;
- steps to reproduce;
- expected result;
- actual result;
- console/network evidence where applicable;
- relevant document/reference names;
- severity: blocker/high/medium/low.

PR #3 can move out of Draft only when all blocker/high findings are resolved and the required Monnify sandbox scenarios have passed or are explicitly deferred for a documented external credential/provider dependency.