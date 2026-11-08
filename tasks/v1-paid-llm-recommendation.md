# v1: LLM recommendation, paid, without losing money

Decided 2026-11-08 in a grilling session. Vocabulary: [GLOSSARY.md](../GLOSSARY.md). Billing rationale: [ADR 0001](../docs/adr/0001-credit-ledger-as-billing-primitive.md).
Each numbered delivery is one commit the owner reviews alone, with `just check` and `just test` green. Stop after each one.

## Decisions (do not re-open without a reason)

| Topic | Decision |
|---|---|
| Step 2 | Stays an LLM for v1 (classifier research parked in docs/classifier-comparison.md) |
| Model | One model for both steps (`SEARCHMARK_MODEL`). Candidates: `openai/gpt-5.6-luna` (baseline 17/20 exact), `openai/gpt-6-luna`, `anthropic/claude-haiku-5-5`. Rule: must reach ≥ baseline exact count on the 50-URL golden set; cheapest passing model wins |
| Golden set | 20 → 50 URLs, stratified over top-level folders, dead pages dropped, each with a note. Owner reviews expected paths before any run |
| Cost guards | Max 2 000 folders per request (413 beyond), `max_tokens=300`, LLM `timeout=30` s. Page content already capped at 15 000 chars |
| Prompt caching | Step 2 message order: system prompt, folder tree, then page analysis last, so the per-account tree is a stable cacheable prefix (OpenAI caches ≥ 1 024 tokens automatically) |
| Spend visibility | Hard monthly spend limit set in the provider console (manual). Real cost per request logged from LiteLLM `response_cost`; Sentry message when one call exceeds `SEARCHMARK_COST_ALERT_USD` (default 0.02) |
| Offer | Freemium: 25 credits once per new account. Paid: one pack (300 credits, ~4 €), no expiry. Subscription deferred to v2 |
| Debit | 1 credit per HTTP 200 of `/recommend`. Fetch or LLM errors: 0. Cache hit, repeated URL, `create_new_folder`: still 1. Balance ≥ 1 checked before, debited after; -1/-2 tolerated |
| Accounts | Live in this API. Postgres via `asyncpg` + `schema.sql` applied at startup (Alembic only at the first real migration). Tables: `account`, `credit_ledger` (append-only, `external_id` unique for idempotent webhooks) |
| Auth | API key per account, shown once, stored hashed, sent as `Authorization: Bearer` |
| Signup | Email + magic link (15 min, single use, token kept in Valkey), key issued after verification. Email through a transactional provider's HTTP API (Resend or Postmark, pick at delivery 4) |
| Payment | Stripe Checkout hosted page + `checkout.session.completed` webhook → ledger line. Stripe Tax on |
| Abuse | Traefik `rateLimit` middleware (labels in compose.production.yml) on a dedicated `/auth` router. No Python rate limiting |
| Docs | Root `model-comparison.md` replaced by `docs/model-comparison.md` with today's prices and golden set scores |

Assumptions to confirm with the extension side: the verify page shows the API key and the user pastes it into the extension (no deep link back into the extension in v1).

## Deliveries

### 0. Shared understanding (this commit)
- [x] GLOSSARY.md
- [x] docs/adr/0001-credit-ledger-as-billing-primitive.md
- [x] docs/classifier-comparison.md: decision line
- [x] tasks/v1-paid-llm-recommendation.md (this file)

### 1. Cost guards, cacheable prompt, cost log, Sentry
- [x] `/recommend`: count folders recursively, 413 when > 2 000 (`SEARCHMARK_MAX_FOLDERS`)
- [x] Both LLM calls go through `_complete`: `max_tokens=300`, `timeout=30`
- [x] `get_folder_recommendation`: tree before analysis in the user message (system, tree, analysis)
- [x] Log `response_cost`, prompt and cached tokens per LLM call; `sentry_sdk.capture_message` when above `SEARCHMARK_COST_ALERT_USD`
- [x] `sentry_sdk.init(dsn=SENTRY_DSN)` (no DSN = disabled); `sentry-sdk` moved to main deps, `prod` group and Dockerfile flag removed
- [x] Tests: 413 on oversized tree; bounded call; cost alert on/off; message order
- [x] Verify: 42 tests green, `pre-commit run -a` green, 3 real step-2 calls on the fixture tree (see Review)

### 2a. Golden set to 50
- [ ] One-off script in the scratchpad (not committed): stratified draw of ~40 leaves over top-level folders, HEAD request to drop dead pages, keep 30
- [ ] Append 30 rows to fixtures/eval/golden.jsonl with `note`
- [ ] Hand back: owner reviews expected paths and notes before any model run

### 2b. Model choice
- [ ] Re-check prices on the official pages the day of the run
- [ ] `SEARCHMARK_MODEL=... uv run python scripts/eval_recommend.py run fixtures/bookmarks.json --set fixtures/eval/golden.jsonl` for the 3 candidates (Anthropic needs `ANTHROPIC_API_KEY`)
- [ ] `compare` the 3 result files; pick cheapest model with exact ≥ baseline
- [ ] Set the default `MODEL`; write `docs/model-comparison.md` (prices, scores, latency, cost per recommendation); delete root `model-comparison.md`
- [ ] If the winner is Anthropic: add `cache_control` on the tree block (LiteLLM passes it through) and re-measure cached tokens

### 3. Postgres, accounts, ledger, key auth
- [ ] `asyncpg` dependency; `app/db.py`: pool from `POSTGRES_*` env, `schema.sql` executed at startup (`CREATE TABLE IF NOT EXISTS`)
- [ ] Schema: `account(id, email unique, api_key_hash unique, created_at)`, `credit_ledger(id, account_id, delta, reason, external_id unique null, created_at)`
- [ ] Auth dependency on `/recommend`: Bearer key → sha256 → account; 401 unknown key; 402 when balance < 1
- [ ] Debit -1 (`reason='recommendation'`) after a successful recommendation
- [ ] `GET /account`: email and balance
- [ ] CLI `searchmark create-account <email>`: inserts account, +25 `signup` line, prints the key once (dev and support tool until delivery 4)
- [ ] Tests against a real Postgres (`POSTGRES_HOST` set → run, else skip); Postgres service container in the CI workflow
- [ ] Verify: local compose up, create account via CLI, `/recommend` with and without key, balance decrements, 402 at 0

### 4. Signup by magic link
- [ ] `POST /auth/signup {email}` → random token, `SETEX token→email 900` in Valkey, email with the verify link via provider HTTP API (`EMAIL_API_KEY`, `EMAIL_FROM`); always 202
- [ ] `GET /auth/verify?token=` → `GETDEL`; create account if new with +25 `signup` line; issue a new key (replaces the old one); minimal HTML page showing the key once
- [ ] Traefik labels in compose.production.yml: router `fastapi-auth` `PathPrefix(\`/auth\`)`, higher priority, `rateLimit` middleware (e.g. average 10/h, burst 5)
- [ ] Tests: signup stores token and calls the mailer (mocked); verify creates account and credits once; second verify with same token → 400
- [ ] Verify: real email received in staging, link works, key authenticates `/recommend`

### 5. Stripe pack
- [ ] `stripe` dependency; `POST /billing/checkout` (auth) → Checkout Session (`STRIPE_PRICE_ID`, `client_reference_id=account.id`, `automatic_tax`), returns URL
- [ ] `POST /billing/webhook`: verify `Stripe-Signature`; on `checkout.session.completed` insert ledger line `+300`, `reason='pack'`, `external_id=event.id` (unique → duplicate deliveries are no-ops)
- [ ] Tests: webhook signature rejected; event credited once even when delivered twice
- [ ] Verify: Stripe test mode end to end with the CLI webhook forwarder; balance goes up by 300

## Review

### Delivery 1 (2026-11-08)
Measured on fixtures/bookmarks.json (894 folders) with gpt-5.6-luna, 3 consecutive step-2 calls:

| call | prompt tokens | cached | completion (incl. reasoning) | cost |
|---|---|---|---|---|
| 1 | 21 782 | 0 | 107 (45 reasoning) | 0.557 ct |
| 2 | 21 782 | 21 779 | 97 (35 reasoning) | 0.055 ct |
| 3 | 21 782 | 21 779 | 109 (38 reasoning) | 0.057 ct |

Step 1 (page summary) costs ~0.05 ct. So one recommendation = ~0.6 ct uncached, ~0.1 ct with a warm tree cache. The tree is 21.8k tokens, not the 10-15k assumed in the research notes (ids are included in the TOON). A 300-credit pack at 4 € costs at most 1.8 € of LLM in the worst case. One earlier CLI run showed 0 cached tokens on a second call ~15 s later: OpenAI caching is best effort, not guaranteed. `max_tokens=300` leaves ~3× headroom over the observed ~110 completion tokens of this reasoning model; a run-away reasoning would surface as an empty-content parse error (500), not as a cost.
