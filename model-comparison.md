# Model Comparison for Searchmark API

## Task Profile

The API performs two LLM tasks:

1. **Web page summarization** - extract title + summary from HTML content (structured JSON output)
2. **Folder classification** - recommend the best folder for a bookmark from a potentially large folder tree (structured JSON output with reasoning)

### Key requirements

- Fine-grained multi-class classification (many folders to choose from)
- Structured JSON output (Pydantic `response_format`)
- Short context (~15K chars page content + folder tree)
- Reasoning ability to discriminate between similar/overlapping categories

### Relevant benchmarks

| Benchmark | Why |
|---|---|
| **MMLU-Pro** | Nuanced understanding and multi-choice discrimination |
| **IFBench** | Instruction following / structured output compliance |
| **Artificial Analysis Intelligence Index** | Composite quality score |

Not relevant: AIME (math), SWE-bench (coding), GPQA Diamond (science).

## Price Comparison (per million tokens)

| Model | Input | Output | Quality Tier | LiteLLM identifier | Notes |
|---|---|---|---|---|---|
| **GPT-4.1** (current) | $2.00 | $8.00 | High | `openai/gpt-4.1` | Current baseline |
| **GPT-4.1 mini** | $0.40 | $1.60 | Mid | `openai/gpt-4.1-mini` | Too weak for folder classification |
| **Claude Sonnet 4.5** | $3.00 | $15.00 | High | `anthropic/claude-sonnet-4-5-20250929` | Same tier, 1.5-2x more expensive |
| **Gemini 3 Pro** | $2.00 | $12.00 | High | `gemini/gemini-3-pro` | Similar input, pricier output |
| **Gemini 3 Flash** | $0.50 | $3.00 | Mid-High | `gemini/gemini-3-flash` | Best value candidate |
| **DeepSeek V3.1** | $0.15 | $0.75 | High | `deepseek/deepseek-chat` | Cheapest high-quality option |
| **DeepSeek V3.2** | $0.03 | ~$1.00 | High | `deepseek/deepseek-chat` | GPT-5 class quality reported |
| **Grok 4.1 Fast** | $0.20 | $0.50 | High | `xai/grok-4.1-fast` | Very cheap, newer model |

> **Note:** LiteLLM identifiers should be verified against [LiteLLM docs](https://docs.litellm.ai/docs/providers) before testing.

## Test Priority

1. **DeepSeek V3.1/V3.2** - 10-30x cheaper than GPT-4.1, reportedly similar quality
2. **Gemini 3 Flash** - optimized for classification tasks, good price/quality ratio
3. **Grok 4.1 Fast** - very cheap, high quality tier

## Test Results

| Model | Folder classification accuracy | Summarization quality | Structured output reliability | Cost per request (est.) | Verdict |
|---|---|---|---|---|---|
| GPT-4.1 (baseline) | | | | | Current |
| DeepSeek V3.1/V3.2 | | | | | |
| Gemini 3 Flash | | | | | |
| Grok 4.1 Fast | | | | | |

## Sources

- [OpenAI API Pricing](https://platform.openai.com/docs/pricing)
- [Claude API Pricing](https://platform.claude.com/docs/en/about-claude/pricing)
- [DeepSeek API Pricing](https://api-docs.deepseek.com/quick_start/pricing)
- [Gemini API Pricing](https://ai.google.dev/gemini-api/docs/pricing)
- [Artificial Analysis Leaderboard](https://artificialanalysis.ai/leaderboards/models)
- [AI API Pricing Comparison - IntuitionLabs](https://intuitionlabs.ai/articles/ai-api-pricing-comparison-grok-gemini-openai-claude)
