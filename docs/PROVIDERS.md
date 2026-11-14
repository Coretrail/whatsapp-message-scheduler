# Providers

## Shipped provider: demo

Only `demo` is available. WhatsApp and email are channel labels used to exercise the scheduler. `DemoProvider` has no network imports, credential loading or filesystem access. It checks `message.consent is True` and returns `accepted` with a deterministic `demo:<attempt-id>` receipt. Health explicitly reports `real_sending: false`. Missing consent returns `failed/consent_required`. Unknown provider names raise an error; there is no automatic real-send fallback.

No tokens, accounts or QR codes are needed. Contact lookup returns an empty list. The application does not validate actual consent evidence; the checkbox is only a per-message simulation guard. Cancelling a schedule prevents future unclaimed work; editing consent to false blocks subsequent simulated attempts. Processing jobs cannot be edited. A real provider will need a central recipient consent/revocation registry checked immediately before dispatch.

## Extension contract

`scheduler/providers/base.py` defines `Provider.send(job: dict) -> Result` and `health() -> dict`. Jobs carry a persistent attempt id, message id, occurrence and message payload. The engine reserves an attempt atomically before calling the provider.

| Result | Required interpretation |
|---|---|
| accepted | Provider has positively acknowledged submission; never claim recipient delivery |
| retry | Definitely no submission occurred; safe to try again, maximum three attempts |
| failed | Definitive rejection; stop this schedule |
| unknown | Submission may have occurred; quarantine and never automatically replay |

A retry gets a new attempt id. Remote deduplication, when supported, must therefore use a stable occurrence key derived from message id and due time, not just an attempt id. The demo receipt is deterministic per attempt. A crashed worker lease expires to unknown. Local idempotency and reservations reduce duplicate work but cannot promise exactly-once delivery to an external system.

To add a future provider, implement the protocol, extend the explicit registry, define channel capabilities and safe health metadata, add consent and provider-specific limits, and test denial, timeout, rate limit, restart and ambiguous acceptance with mocked HTTP. Real sending must require explicit activation. Changing the internal Docker network to permit external access is a separate deliberate deployment change. Never distribute a connector without checking authorisation, applicable platform terms, licences and rights.

## Official WhatsApp Business Cloud API: future integration only

**Not implemented, configured or tested against Meta in 0.1.0.** The existing free-text editor cannot simply be connected to the Cloud API. A future integration needs business onboarding, a registered business phone identity, appropriate access tokens/permissions, protected credential provisioning and a versioned official API client.

Outside the permitted customer-service window, proactive messaging generally requires approved message templates; scheduling a free-text message does not establish a valid window. A future implementation must model template name, language, approved parameters and current eligibility, and re-check those rules at dispatch. Consent and opt-out obligations, account quality, business/category restrictions, messaging limits and pricing apply independently of this scheduler's local rate cap. Limits vary by account and may change; this release supplies no universal quota or pricing promise. Acceptance by an API is not a delivery receipt: verified webhooks and reconciliation would be required.

Official references reviewed on 2026-11-14: [platform documentation](https://developers.facebook.com/documentation/business-messaging/whatsapp/overview), [message templates](https://developers.facebook.com/docs/graph-api/reference/whats-app-business-account/message_templates/) and [Business Messaging Policy](https://whatsappbusiness.com/policy/). Read the current official rules before implementing an integration. This is independent community software with no WhatsApp/Meta affiliation.

Unofficial browser/session bridges, personal-account automation and existing third-party account sessions are not included. No distribution permission for such connectors is implied.
