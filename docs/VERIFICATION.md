# Verification record — 0.1.0 local release candidate

Prepared on 2026-11-14. This is evidence for local review, not a published release or a guarantee of absence of all vulnerabilities.

## Scope

The public tree was assembled from a source allowlist, without the original Git directory, operational databases, backups, secrets, logs, previous screenshots, account sessions or private deployment files. Private provider and contact integrations were removed. A new Git repository is initialised independently. All sending during validation is simulated; no real provider is shipped or tested.

## Checks completed

| Check | Result |
|---|---|
| Python engine/API/safety suite in Docker with network disabled | 35 passed |
| Initial administrator setup | Generated secret, mode 0600, existing config never overwritten |
| Clean Compose startup | API, worker and unprivileged gateway healthy; own volumes/networks |
| Actual timed worker processing | Simulated receipt, one attempt with repeated idempotent API create |
| Recurrence and failure recovery | Unit tests cover DST, weekdays/month/year, concurrent claims, bounded retries, unknown timeout, crash lease expiry, hourly cap and long downtime |
| Restart persistence | Schedule, history and changed administrator password survive actual API/worker restart |
| Backup and actual isolated restore switch | Consistent SQLite snapshot; restored queue quarantined, sessions invalidated, accepted history retained |
| Browser desktop/mobile | Login, draft, preview, edit, schedule, recurrence/calendar and mobile form; no JavaScript errors or external requests; no horizontal overflow at 393px |
| Docker artifact review | Distinct application image names by Compose project; project/dependency licences present in runtime image |
| Screenshots | Newly captured with fictional data; PNGs have no text/EXIF metadata |
| Dependency audits | npm audit and pip-audit runtime/development requirements: zero known vulnerabilities after updates |
| Gitleaks files | Zero findings in allowlisted source tree |
| Privacy checks | No remaining configured private-network, private-key, operational database or unapproved contiguous phone indicators |

One deprecation warning remains in the tests: Starlette recommends the optional `httpx2` client instead of `httpx`. Tests pass; no runtime integration uses either client for sending.

An independent read-only review found no Critical issues. Two Important packaging issues (shared mutable Docker image tag and omitted runtime licence notices) were reproduced by failing checks and corrected. Minor PWA wording and npm licence metadata were also corrected. The provider registry and recovery quarantine were reviewed.

## Publication gates and limits

Full new Git history and every object, including unreachable objects, are also scanned after the local root commit. The final local delivery report records the exact commit, manifest, SHA-256 values and final audit outputs. No push, repository creation or hosted workflow run is part of this preparation.

Original source ownership/authority to grant MIT remains the owner's confirmation before publication. Dependency licence metadata and retained notices support the proposed licence but do not establish authorship of supplied source. Base-image operating-system packages have not been exhaustively checked with a container CVE scanner. Windows/macOS Docker Desktop and real-provider interoperability are unverified. A future Cloud API integration requires a separate implementation, platform-policy review and explicit real-message test authorisation.
