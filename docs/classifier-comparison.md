# Classifier vs LLM for Folder Recommendation

Research notes, 2026-10-24. Question: should step 2 (pick a folder) use a classifier instead of an LLM? Step 1 (page summary) is generative and stays an LLM.

## The folder tree (fixtures/bookmarks.json)

- 894 folders, 2795 bookmarks, depth 1 to 6 (most at depth 3-4)
- Widest node: 94 children (`toolbar/Computing`)
- Duplicate leaf names: 10× `Tools`, 7× `Security`, 6× `Design`. The label must be the **full path**, never the leaf name.
- 861 folders hold bookmarks, so each existing bookmark is a free labelled example (url → folder).

## Options

| | LLM (current) | Hosted decision model (Jev, OpenAI Decisions, Liquid d1, Perplexity decider) | Embeddings + reranker (self-hosted) |
|---|---|---|---|
| Accuracy | Unknown. Sees all 894 paths at once and can arbitrate between the 10 `Tools`. | Jev: 0.99 → 0.91 top-1 from 5 to 150 options (CLINC-150). 13% of answers flip when options are reordered. | BTZSC (38 models, 2026): rerankers beat 4-12B LLMs in zero-shot classification. Not compared against frontier LLMs. |
| Many labels | Native, 894 paths ≈ 10-15k tokens. | Hard cap of **255 options** everywhere it is published. Needs 4 parallel chunks + a rerank call, or a tree walk (3-6 sequential calls, greedy errors unrecoverable). | Unlimited. Embed 894 paths once, top-20 by cosine, reranker picks. |
| "No folder fits" | Weak (self-reported). | Choice `confidence` is a dispersion statistic, not correctness. TypeSafe itself says an "other" option works poorly; use a separate yes/no question. | Reranker P(yes) of top-1 plus top-1/top-2 margin, threshold calibrated on own data. |
| Cost / self-host | 10-15k tokens per call. Not self-hostable. | ~$0.0003-0.0015 per bookmark. Jev not self-hostable (signups paused Sept 2026). Perplexity decider (Apache 2.0, 27B) and elephant-1 (MIT, 9B) are, GPU needed. | Two 0.6B Apache 2.0 models, CPU. |

Candidate models for the self-hosted pipeline: `Qwen/Qwen3-Embedding-0.6B` + `Qwen/Qwen3-Reranker-0.6B`. Alternative stage-2 scorer: `knowledgator/gliclass-v4-edge` (435M, CPU-targeted). Avoid Jina models (CC-BY-NC) and NLI/DeBERTa over 861 labels (one pass per label).

## Conclusions

1. Decision models are the wrong fit here: the 255 cap forces a decomposition that erases their simplicity, and their confidence does not detect "none fits".
2. The real challenger is embeddings + reranker. Its one weakness is stage-1 recall: if the right folder is not in the top-20, nothing recovers it.
3. Hybrid worth testing: embeddings shrink 894 paths to 20, the current LLM picks among those. 40× smaller prompt, minimal code change, same recall risk.
4. Only an eval on our own bookmarks can rank these. No published benchmark covers ~900 hierarchical, user-specific labels.

## Experiment order

1. Eval set from existing bookmarks, run against the current LLM (baseline). See `scripts/eval_recommend.py`.
2. **recall@20 of embeddings alone** on all 2795 bookmarks. No LLM call, minutes on CPU. Above ~90% → options 3 and 4 are open; below → the LLM stays.
3. Hybrid: embeddings top-20 → current LLM.
4. Embeddings → reranker, no LLM in step 2.

## Not verified

- CPU latency of a 0.6B reranker: nobody publishes it. Measure before committing.
- OpenAI Decisions' 255 limit comes from one SDK docstring. Liquid d1 limits are unpublished.
- No paper tests path strings ("A/B/C") as labels directly.

## Sources

- [BTZSC benchmark](https://arxiv.org/html/2603.11991)
- [Jev option-count sweep, CLINC-150](https://arxiv.org/abs/2610.00346)
- [TypeSafe docs and cookbooks](https://docs.typesafe.ai)
- [FoRC4CL: hybrid zero-shot on a 181-label taxonomy](https://ceur-ws.org/Vol-3977/NSLP-07.pdf)
- [Qwen3-Embedding-0.6B](https://huggingface.co/Qwen/Qwen3-Embedding-0.6B), [Qwen3-Reranker-0.6B](https://huggingface.co/Qwen/Qwen3-Reranker-0.6B), [GLiClass-v4-edge](https://huggingface.co/knowledgator/gliclass-v4-edge)
- [Artificial Analysis Decision Index](https://benchlm.ai)
- [Open decision models survey](https://redreamality.com/blog/open-decision-models-2026-survey-benchmarks/)
