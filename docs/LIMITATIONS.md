# Limitations and roadmap

0.1.0 is a demo release, not a production WhatsApp delivery service.

Implemented: authenticated single administrator, message CRUD/drafts, preview, cancellation/duplication, daily/weekday/weekly/monthly/yearly recurrence, persistent SQLite queue/history, concurrent-worker reservations, idempotency, bounded retry logic, global hourly attempt limit, overdue/uncertain quarantine, consistent snapshot/recovery and responsive European Portuguese UI.

Not implemented: any real provider (including Cloud API, Gmail and SMTP), delivery/receipt webhooks, approved template editor, automatic customer-service-window tracking, full consent evidence/central opt-out registry, recipient-level quotas, media, multi-user roles, timezone choice, UI language selection, PWA/offline mode, automatic encrypted/remote backups and retention, password-reset UI, anonymous demo hosting or multi-tenant operation.

Engine safety paths for retries and ambiguous results are exercised with synthetic providers in tests; the shipped demo provider itself only accepts or refuses missing consent. Fixed scheduling zone is Europe/Lisbon. Monthly/yearly recurrences skip nonexistent dates; DST gaps are skipped, repeated hours use the first occurrence. A delayed job beyond tolerance needs confirmation; recurrence does not catch up by sending a burst. At most 1,000 active schedules and 1,000 displayed calendar occurrences are supported. Edits to paused messages resume scheduling unless saved as drafts. History is local operational evidence, not tamper-proof audit storage.

Before adding a real provider: centralise consent/revocation and retention; build template/window eligibility and provider quotas; implement secure credential lifecycle and verified webhooks; review platform terms and rights; model timeout reconciliation and stable occurrence deduplication; explicitly permit egress; repeat all isolated tests. No real sending should be added silently.
