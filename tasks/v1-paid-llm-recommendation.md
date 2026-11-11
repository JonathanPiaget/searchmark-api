# v1: LLM recommendation, paid, without losing money

Decided 2026-11-08 in a grilling session. Vocabulary: [GLOSSARY.md](../GLOSSARY.md). Billing rationale: [ADR 0001](../docs/adr/0001-credit-ledger-as-billing-primitive.md).
Each numbered delivery is one commit the owner reviews alone, with `just check` and `just test` green. Stop after each one.

## Decisions (do not re-open without a reason)

| Topic | Decision |
|---|---|
| Step 2 | Stays an LLM for v1 (classifier research parked in docs/classifier-comparison.md) |
| Model | One model for both steps (`SEARCHMARK_MODEL`). Candidates: `openai/gpt-5.6-luna` (baseline 17/20 exact), `openai/gpt-6-luna`, `anthropic/claude-haiku-5-5`. Rule: must reach ≥ baseline exact count on the 50-URL golden set; cheapest passing model wins |
| Golden set | 20 → 50 URLs, stratified over top-level folders, dead pages dropped, each with a note. Owner reviews expected paths before any run |
| Cost guards | Max 2 000 folders per request (413 beyond), `max_tokens=1000` (was 300 until 2026-11-11, see Review), LLM `timeout=30` s. Page content already capped at 15 000 chars |
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

## Open points (owner's call, not yet decided)

- **Pack price.** 300 credits / 4 € is a placeholder used for margin maths only. The owner wants a real margin; re-discuss before delivery 5. Worst-case LLM cost of 300 credits is 1.8 € uncached, ~0.3 € with a warm cache; Stripe takes ~0.30 € + 2 % (+0.5 % Stripe Tax).
- **Owner's own account must be free.** The extension is first of all for the owner's personal use. Proposed: no special code path; the delivery-3 CLI `create-account` takes `--credits N` and the owner grants himself a large ledger line with `reason='owner'`. Alternative if a code path is wanted later: an `unlimited` flag on `account`. Confirm with the owner at delivery 3.
- **Key into the extension.** Assumed: the verify page shows the API key once and the user pastes it into the extension (no deep link back into the extension in v1). Confirm with the extension side before delivery 4.
- **Email provider.** Resend or Postmark, pick at delivery 4 (free tier and domain verification to check).

## Facts for the next agent (found while working, not obvious from the code)

- Secrets live in `.envs/.local/.fastapi` (`OPENAI_API_KEY`, `REDIS_URL`); the CLI and the eval script load it with dotenv. `ANTHROPIC_API_KEY` goes there too for the Haiku run. `.envs/.local/.postgres` holds `POSTGRES_*`.
- CI (`.github/workflows/main.yml`) runs pytest inside `compose.local.yml` (`docker compose exec fastapi`), and that compose already has Postgres and Valkey. DB tests need no extra CI service, only the `POSTGRES_*` env the fastapi service already receives.
- Traefik is the edge, no Cloudflare in front. The `csrf@file` middleware referenced in compose.production.yml is defined in a file provider on the server, not in this repo. New middlewares (rateLimit) can be plain labels.
- Sentry is initialised in `app/main.py` but `SENTRY_DSN` is not set anywhere yet; the production env file is on the server.
- `gpt-5.6-luna` and `gpt-6-luna` are reasoning models: reasoning tokens are billed as output and count against `max_tokens`. Measured per step-2 call on 2026-11-11: 46-138 on 5.6, 88-300+ on 6.
- The folder tree is 21.8k tokens for 894 folders (~24 tokens per folder), so `SEARCHMARK_MAX_FOLDERS=2000` caps a step-2 prompt at ~50k tokens ≈ 1 ct uncached on luna.
- Model prices, caching rules per provider and exclusion reasons are in `docs/model-comparison.md`. Classifier alternatives (parked) in `docs/classifier-comparison.md`.
- Vocabulary in `GLOSSARY.md`; `scripts/eval_recommend.py run --set fixtures/eval/golden.jsonl` writes `fixtures/eval/golden-<model>.jsonl`, `compare` prints the side-by-side.

## Deliveries

### 0. Shared understanding (this commit)
- [x] GLOSSARY.md
- [x] docs/adr/0001-credit-ledger-as-billing-primitive.md
- [x] docs/classifier-comparison.md: decision line
- [x] tasks/v1-paid-llm-recommendation.md (this file)

### 1. Cost guards, cacheable prompt, cost log, Sentry
- [x] `/recommend`: count folders recursively, 413 when > 2 000 (`SEARCHMARK_MAX_FOLDERS`)
- [x] Both LLM calls go through `_complete`: `max_tokens=300` (raised to 1000 on 2026-11-11), `timeout=30`
- [x] `get_folder_recommendation`: tree before analysis in the user message (system, tree, analysis)
- [x] Log `response_cost`, prompt and cached tokens per LLM call; `sentry_sdk.capture_message` when above `SEARCHMARK_COST_ALERT_USD`
- [x] `sentry_sdk.init(dsn=SENTRY_DSN)` (no DSN = disabled); `sentry-sdk` moved to main deps, `prod` group and Dockerfile flag removed
- [x] Tests: 413 on oversized tree; bounded call; cost alert on/off; message order
- [x] Verify: 42 tests green, `pre-commit run -a` green, 3 real step-2 calls on the fixture tree (see Review)

### 2a. Golden set to 50
- [x] One-off script in the scratchpad (not committed): stratified draw of ~40 leaves over top-level folders, HEAD request to drop dead pages, keep 30
- [x] Append 30 rows to fixtures/eval/golden.jsonl with `note`
- [x] Hand back: owner reviews expected paths and notes before any model run

### 2b. Model choice
- [ ] Re-check prices on the official pages the day of the run
- [ ] `SEARCHMARK_MODEL=... uv run python scripts/eval_recommend.py run fixtures/bookmarks.json --set fixtures/eval/golden.jsonl` for the 3 candidates (Anthropic needs `ANTHROPIC_API_KEY`)
- [ ] `compare` the 3 result files; pick cheapest model with exact ≥ baseline
- [ ] Set the default `MODEL`; fill the results table in `docs/model-comparison.md` (root `model-comparison.md` already removed)
- [ ] If the winner is Anthropic: add `cache_control` on the tree block (LiteLLM passes it through) and re-measure cached tokens

### 3. Postgres, accounts, ledger, key auth
- [ ] `asyncpg` dependency; `app/db.py`: pool from `POSTGRES_*` env, `schema.sql` executed at startup (`CREATE TABLE IF NOT EXISTS`)
- [ ] Schema: `account(id, email unique, api_key_hash unique, created_at)`, `credit_ledger(id, account_id, delta, reason, external_id unique null, created_at)`
- [ ] Auth dependency on `/recommend`: Bearer key → sha256 → account; 401 unknown key; 402 when balance < 1
- [ ] Debit -1 (`reason='recommendation'`) after a successful recommendation
- [ ] `GET /account`: email and balance
- [ ] CLI `searchmark create-account <email> [--credits N]`: inserts account, +N `signup`/`owner` line (default 25), prints the key once (dev, support and owner's free account)
- [ ] Tests against a real Postgres (`POSTGRES_HOST` set → run, else skip); CI already runs pytest inside compose.local.yml which has Postgres
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

### Fix before delivery 2b (2026-11-11)
The first golden-set runs on 50 URLs crashed on both OpenAI models: step 2 returned an empty answer (`finish_reason=length`, 300 of 300 completion tokens spent on reasoning), which is a 500 on `/recommend`. Seen 1 time in 23 step-2 calls on gpt-5.6-luna and 1 in 16 on gpt-6-luna; reproduced 2 times in 12 on gpt-6-luna for one URL, with `max_tokens=1000` the same call answered using 227 tokens. Cap raised to 1000: worst case +0.084 ct per call on gpt-5.6-luna, +0.035 ct on gpt-6-luna. The eval script now scores an LLM failure as a miss instead of stopping.

Also measured: 0 prompt-cache hits in 37 step-2 calls during these runs (calls 10-20 s apart). Margin maths should use the uncached cost (~0.6 ct on gpt-5.6-luna).
