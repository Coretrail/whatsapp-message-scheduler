# Contributing

Use a dedicated branch and an isolated demo installation. Never include real recipients, messages, tokens, sessions, QR codes, databases, private addresses or account screenshots. Test fixtures use the reserved `+1 202 555 0123` fictional number and `example.invalid` email addresses.

Build and run tests:

```sh
docker build --target test -t scheduler-tests .
docker run --rm --network none scheduler-tests
cd frontend
npm ci
npm run build
```

For browser smoke, install Playwright Chromium and its dependencies, then use `DEMO_URL`/`DEMO_PASSWORD` with `npm run test:e2e` against a fresh isolated instance. It creates fictional schedules and drafts. No tests should send real messages.

Keep provider implementations behind the explicit protocol/registry. Document supported capabilities and failure semantics. A provider change must test definitive rejection, known-safe retry, ambiguous timeout, crash/restart, consent/revocation and limits. Do not introduce private account automation or enable network sending by default. New dependencies require a licence and vulnerability review. Preserve notices.

PRs should explain the user-visible change and actual verification performed. Run privacy checks and Gitleaks before proposing publication. Contributions are offered under the project's MIT licence; only submit work you have rights to distribute. Report security issues privately as described in SECURITY.md.
