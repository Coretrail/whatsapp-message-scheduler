# Security and privacy guide

This release is an offline demonstration scheduler. Use fictional data even though there is no sending. Anyone with access to the host or Docker administration can read its environment and volume.

## Included controls

- Generated initial password; PBKDF2-HMAC-SHA256 with a random salt and 600,000 iterations; persistent hash only in app configuration.
- HttpOnly, SameSite=Strict sessions (12 hours), CSRF checks on writes, exact origin checks and login throttling (six failed attempts per address in 15 minutes).
- Cookie Secure option for HTTPS, no trusted forwarded headers, response security headers and no API response caching.
- Non-root containers, read-only root filesystem, limited resources, dropped capabilities, named volume and loopback binding.
- Internal Docker network, explicit demo-only provider, no account credentials or external contacts.
- Atomic SQLite claims, idempotency keys, optimistic edit versions, global attempt limit, bounded known-safe retries, uncertain-result quarantine and safe restore.

## Operator responsibilities and limits

Keep `.env`, auth configuration, SQLite files, snapshots and session material outside Git and releases. Backups contain message content and recipient fields even when sessions have been removed. Store them encrypted using a separately managed tool, restrict access and verify recovery. Encryption, remote backup and automatic retention are not built in. Treat snapshots as sensitive, trusted local input; the recovery tool is not a sandbox for hostile SQLite files.

Use HTTPS before enabling remote access. Origin and cookie settings must match the browser address. Login throttling is local and is not a replacement for an internet-facing proxy's rate limits. There is one administrator account, no role separation or independently tamper-proof audit log. Password changes invalidate other sessions; the current session remains active. Do not use the demo checkbox as proof of legal consent or as a global opt-out registry. There is no real provider to enable in this release.

The public API does not include the private integration API. Application logs avoid message payloads and account tokens, but operational metadata remains in the database. Define your own retention and deletion policy before storing personal data. The provided .gitignore is a guard, not a secret scanner.

## Release audit procedure

1. Review an explicit source allowlist; exclude runtime volumes, databases, backups, logs, dependencies, build output and local credentials.
2. Run Gitleaks against files and full history, plus `scripts/privacy_check.py` against tracked files and all Git objects, including unreachable ones.
3. Run `git fsck --full --no-reflogs` and review every unreachable object. Never copy private Git metadata into a public repository.
4. Inspect screenshots visually; they must use fictional identities and contain no account secrets or sessions.
5. Run dependency audits, unit/safety tests and isolated Docker/browser/recovery tests. Keep redacted evidence locally.

See [SECURITY.md](../SECURITY.md) for vulnerability reporting and [verification](VERIFICATION.md) for the preparation results. Automated scanning does not prove absence of all sensitive information.
