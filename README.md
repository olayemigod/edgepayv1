### EdgePay

Universal payment orchestration layer for Frappe, ERPNext, POSnext, and EdgeSuite apps

### Installation

You can install this app using the [bench](https://github.com/frappe/bench) CLI:

```bash
cd $PATH_TO_YOUR_BENCH
bench get-app $URL_OF_THIS_REPO --branch develop
bench install-app edgepayv1
```

### Contributing

This app uses `pre-commit` for code formatting and linting. Please [install pre-commit](https://pre-commit.com/#installation) and enable it for this repository:

```bash
cd apps/edgepayv1
pre-commit install
```

Pre-commit is configured to use the following tools for checking and formatting your code:

- ruff
- eslint
- prettier
- pyupgrade
### CI

This app can use GitHub Actions for CI. The following workflows are configured:

- CI: Installs this app and runs unit tests on every push to `develop` branch.
- Linters: Runs [Frappe Semgrep Rules](https://github.com/frappe/semgrep-rules) and [pip-audit](https://pypi.org/project/pip-audit/) on every pull request.


mit

---

### Developer Documentation

#### 1. Execution Modes: Simulated vs. Sandbox vs. Live
* **Simulated Mode (Default in Tests)**: Uses `SimulatedMonnifyClient` to return mock success/pending responses instantly. No network connections are initiated.
* **Sandbox Mode**: Executes network requests against Monnify's sandbox endpoints (`https://sandbox.monnify.com/api`). Requires sandbox credentials and live-call gating enabled.
* **Live Mode**: Executes network requests against Monnify's production endpoints (`https://api.monnify.com/api`). Requires live credentials and live-call gating enabled.

#### 2. Live-Provider-Call Gating
To prevent accidental external calls, a strict multi-tier gating system is enforced:
1. `EdgePay Settings` -> `Enable EdgePay` must be Checked.
2. `EdgePay Settings` -> `Allow External HTTP Calls` must be Checked (Defaults to Unchecked/Disabled).
3. The specific `EdgePay Provider` must be enabled.
4. Credentials (`api_key` and `secret_key`) must be configured on the provider.
If any gating check fails, the live client throws a validation error immediately.

#### 3. Authentication Caching
Bearer tokens obtained via Basic Auth POST request to `/v1/auth/login` are cached in Redis via `frappe.cache()`.
* Cache keys are hashed and unique to the provider name and credential pair.
* Tokens are cached with a **5-minute safety buffer** subtracted from the provider-returned `expiresIn` duration.
* Expired tokens are refreshed transparently on the next request.
* Tokens are never stored in the database, logged, or returned in whitelisted APIs.

#### 4. Safety Warnings & Tests
* **No Network Calls in Tests**: All unit tests run with `allow_external_http_calls` disabled by default. Live integration tests patch out the `requests` library to ensure network requests are never sent.
* **Accounting & Fulfillment Excluded**: Real transactions do NOT mutate ERPNext/accounting records (e.g. Sales Invoices, Journal Entries, GL Entries) in this infrastructure layer. Any automatic accounting mutations must wait for subsequent connector phases.

#### 5. Required Monnify Configuration
- **API Key**: Found on the Monnify dashboard. Saved securely as a `Password` field.
- **Secret Key**: Found on the Monnify dashboard. Saved securely as a `Password` field.
- **Contract Code**: Monnify contract code (required for live/sandbox calls).
- **Webhook Signature**: Computed locally using HMAC-SHA512.

