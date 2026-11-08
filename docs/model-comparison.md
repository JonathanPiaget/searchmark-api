# Model comparison

Which LLM runs both steps (page analysis, folder recommendation). Rule from the plan: a candidate must reach at least the baseline's exact count on the 50-URL golden set; the cheapest passing model wins. Prices below were read on the official pages on 2026-11-08 and **must be re-checked the day of the runs** (the Luna price was cut on 2026-07-30; the Gemini promo ends 2026-12-31).

## Measured cost profile (fixtures/bookmarks.json, 894 folders)

- Step 2 prompt: 21 782 tokens (TOON tree with ids). Completion ~100 tokens, of which 35-45 are reasoning tokens on gpt-5.6-luna.
- Step 1 (page summary, ≤ 15 000 chars): ~4k tokens, ~0.05 ct.
- One recommendation with gpt-5.6-luna: ~0.6 ct uncached, ~0.1 ct when the tree prefix hits the prompt cache (21 779 of 21 782 tokens cached on the 2nd call).

## Candidates (USD per 1M tokens, standard tier)

| LiteLLM id | Input | Cached input | Output | JSON schema | AA Intelligence Index v5 | Note |
|---|---|---|---|---|---|---|
| `openai/gpt-5.6-luna` (current) | 0.20 | 0.02 | 1.20 | yes | 35 xhigh / 16 non-reasoning | Baseline 17/20 exact. Artificial Analysis lists it as deprecated in favour of GPT-6 Luna: not verified on OpenAI's side |
| `openai/gpt-6-luna` | 0.10 | 0.01 | 0.50 | yes | 28 | Cheapest current OpenAI model |
| `anthropic/claude-haiku-5-5` | 0.10 | 0.01 read, 0.125 write | 0.50 | yes | 36 max / 25 medium | Best index per dollar found. Caching needs `cache_control` on the tree block (LiteLLM passes it through), min prefix 512 tokens |
| `gemini/gemini-3.8-flash` | 0.75 (promo) | 0.075 | 3.75 | yes | 31 high | 4-7× the others; only worth running if nothing cheaper passes |

Excluded: `deepseek/deepseek-flash` (no json_schema mode, empty-content failure mode in JSON mode, despite 0.30/1.20 and 98 % cache discount), `gemini/gemini-3.5-flash-lite` (index 12, too weak for 900-way classification), xAI (`grok-4.3` 1.25/2.50, no "fast" model any more), `openai/gpt-5.4-mini` (0.75/4.50, no index found).

Sources: https://developers.openai.com/api/docs/pricing · https://claude.com/pricing · https://aistudio.google.com/docs/pricing · https://api-docs.deepseek.com/quick_start/pricing/ · https://docs.x.ai/developers/models · https://docs.litellm.ai/docs/providers · https://docs.litellm.ai/docs/completion/json_mode · https://artificialanalysis.ai/leaderboards/models

## Prompt caching per provider

| Provider | Opt-in | Min prefix | Discount | How to see hits |
|---|---|---|---|---|
| OpenAI | automatic; GPT-5.6+ bills cache writes 1.25× (30 min TTL) | 1 024 tokens | reads 0.1× | `usage.prompt_tokens_details.cached_tokens` (logged by `_complete`) |
| Anthropic | explicit `cache_control: {"type": "ephemeral"}` on the block | 512 (Haiku/Sonnet 5.5) | reads 0.1× (Haiku), writes 1.25× | `cache_creation_input_tokens`, `cache_read_input_tokens` |
| Gemini | implicit on 2.5+; explicit = billed storage | 4 096 (3.8 Flash) | 0.1× | usage metadata |
| DeepSeek | always on | undocumented | ~0.02× | `prompt_cache_hit_tokens` |

Caching is best effort everywhere: one CLI run on 2026-11-08 got 0 cached tokens on a second identical prefix 15 s later, three consecutive calls 5 s apart all hit.

## Golden set results (50 URLs)

To fill at delivery 2b with `uv run python scripts/eval_recommend.py compare fixtures/eval/golden-*.jsonl`.

| Model | exact | related | miss | median step-2 ms | cost / recommendation uncached | Verdict |
|---|---|---|---|---|---|---|
| gpt-5.6-luna | 17/20 (old set) | 0 | 3 | 2 180 | 0.6 ct | baseline |
| gpt-6-luna | | | | | | |
| claude-haiku-5-5 | | | | | | |

Baseline misses on the 20-URL set: trivy (chose Security/Scanners over Docker/Tools/Security), marcel (chose Docker/Tools over Humour), pgcli (chose DataBases/PgSQL/Tools over DataBases/CLIs).
