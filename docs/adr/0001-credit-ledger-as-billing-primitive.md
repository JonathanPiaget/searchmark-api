---
status: accepted
date: 2026-11-08
---

# Credits in an append-only ledger are the only billing primitive

The paid feature must be profitable from the first customer while letting people try it. We bill in credits (one credit = one recommendation, debited only on a successful response), keep them in an append-only ledger per account whose sum is the balance, and sell them only as prepaid packs with no expiry. A subscription was considered and deferred: usage is bursty (a big import, then occasional saves), prepaid money arrives before any LLM cost is incurred, unused credits are pure margin, and a subscription can be added later as a recurring credit grant on the same ledger without touching the rest. Payment-provider fees, not LLM tokens (measured 2026-11-08 on an 894-folder tree with gpt-5.6-luna: 0.6 cents per recommendation uncached, 0.1 cents when the folder tree hits the provider's prompt cache), dominate the cost of a sale, which is why one pack size and no micro-payments.

## Consequences

- Every webhook or signup writes one ledger line keyed by its external event id, so retries are idempotent for free.
- The balance check happens before the call and the debit after success, so a burst of concurrent calls can take an account to -1 or -2. Accepted: the loss is a fraction of a cent and the account is blocked on its next call.
