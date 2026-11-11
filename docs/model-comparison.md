# Model comparison

Which LLM runs both steps (page analysis, folder recommendation). Rule from the plan: a candidate must reach at least the baseline's exact count on the 50-URL golden set; the cheapest passing model wins. Prices below were read on the official pages on 2026-11-08 and **must be re-checked the day of the runs** (the Luna price was cut on 2026-07-30; the Gemini promo ends 2026-12-31).

## Measured cost profile (fixtures/bookmarks.json, 894 folders)

- Step 2 prompt: 21 782 tokens (TOON tree with ids). Completion ~100 tokens, of which 35-45 are reasoning tokens on gpt-5.6-luna.
- Step 1 (page summary, ≤ 15 000 chars): ~4k tokens, ~0.04 ct.
- One recommendation with gpt-5.6-luna: ~0.5 ct uncached, ~0.08 ct when the tree prefix hits the prompt cache (21 779 of 21 782 tokens cached on the 2nd call).

## Candidates (CHF per 1M tokens, standard tier)

Providers bill in USD; the official USD list price is in parentheses. Converted on 2026-11-11 at 1 USD = 0.830 CHF. "ct" in this file means Swiss centimes.

| LiteLLM id | Input | Cached input | Output | JSON schema | AA Intelligence Index v5 | Note |
|---|---|---|---|---|---|---|
| `openai/gpt-5.6-luna` (previous default) | 0.166 ($0.20) | 0.017 ($0.02) | 1.00 ($1.20) | yes | 35 xhigh / 16 non-reasoning | Baseline 17/20 exact. Artificial Analysis lists it as deprecated in favour of GPT-6 Luna: not verified on OpenAI's side |
| `openai/gpt-6-luna` | 0.083 ($0.10) | 0.008 ($0.01) | 0.415 ($0.50) | yes | 28 | Cheapest current OpenAI model |
| `anthropic/claude-haiku-5-5` | 0.083 ($0.10) | 0.008 read ($0.01), 0.104 write ($0.125) | 0.415 ($0.50) | yes | 36 max / 25 medium | Best index per dollar found. Caching needs `cache_control` on the tree block (LiteLLM passes it through), min prefix 512 tokens |
| `gemini/gemini-3.8-flash` | 0.62 ($0.75, promo) | 0.062 ($0.075) | 3.11 ($3.75) | yes | 31 high | 4-7× the others; only worth running if nothing cheaper passes |

Excluded: `deepseek/deepseek-flash` (no json_schema mode, empty-content failure mode in JSON mode, despite 0.25/1.00 CHF and 98 % cache discount), `gemini/gemini-3.5-flash-lite` (index 12, too weak for 900-way classification), xAI (`grok-4.3` 1.04/2.08 CHF, no "fast" model any more), `openai/gpt-5.4-mini` (0.62/3.74 CHF, no index found).

Sources: https://developers.openai.com/api/docs/pricing · https://claude.com/pricing · https://aistudio.google.com/docs/pricing · https://api-docs.deepseek.com/quick_start/pricing/ · https://docs.x.ai/developers/models · https://docs.litellm.ai/docs/providers · https://docs.litellm.ai/docs/completion/json_mode · https://artificialanalysis.ai/leaderboards/models

## Prompt caching per provider

| Provider | Opt-in | Min prefix | Discount | How to see hits |
|---|---|---|---|---|
| OpenAI | GPT-5.6+: automatic mode caches the whole prompt up to the end of the last user message, so it only hits on identical requests. We use explicit mode with `prompt_cache_breakpoint` on the tree block. Writes billed 1.25× (30 min TTL) | 1 024 tokens | reads 0.1× | `usage.prompt_tokens_details.cached_tokens` (logged by `_complete`) |
| Anthropic | explicit `cache_control: {"type": "ephemeral"}` on the block | 512 (Haiku/Sonnet 5.5) | reads 0.1× (Haiku), writes 1.25× | `cache_creation_input_tokens`, `cache_read_input_tokens` |
| Gemini | implicit on 2.5+; explicit = billed storage | 4 096 (3.8 Flash) | 0.1× | usage metadata |
| DeepSeek | always on | undocumented | ~0.02× | `prompt_cache_hit_tokens` |

The 0 cached tokens seen on 2026-11-08 for a second call were not bad luck: automatic mode cannot hit when the page differs. With the explicit breakpoint, 7 of 7 follow-up calls on different pages hit on 2026-11-11.

## Golden set results (50 URLs)

Run on 2026-11-11, result files in `fixtures/eval/golden-<model>.jsonl` (`uv run python scripts/eval_recommend.py compare fixtures/eval/golden-*.jsonl`). The two OpenAI models were run twice to measure noise; the committed files are the first pass. Costs are measured averages per recommendation (step 1 + step 2) on the 894-folder tree: cold = tree not in the prompt cache, warm = tree cached.

| Model | exact | related | miss | median step-2 ms | cost / recommendation | Verdict |
|---|---|---|---|---|---|---|
| gpt-5.6-luna | 33 (2nd pass 35) | 2 | 15 | 2 596 | 0.53 ct cold, 0.11 ct warm | baseline |
| gpt-6-luna | 33 (2nd pass 34) | 5 | 12 | 3 149 | 0.26 ct cold, 0.05 ct warm | **chosen**: ties the baseline within noise at half the cost |
| claude-haiku-5-5 | 24 | 13 | 13 | 2 440 | 0.31 ct (no cache marker) | rejected: 9 fewer exact, often stops one level above the right folder |

Noise: between two passes of the same model 3 to 5 verdicts flip and the exact count moves by 1 or 2, so differences of that size mean nothing. Nine URLs are missed by all three models (the page alone does not say why the owner filed it there, e.g. `Emploi/Entreprises intéressantes`, `Server/Utils`, `SearchMark/Tools`): they are the ceiling of this approach, not a model weakness. No empty answers in 500 calls with `max_tokens=1000`.
