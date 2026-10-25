# How AI ingests huge, fast-changing, concurrent context — landscape (Oct 2026) and new ideas

Prepared for Mahimn Patel. Date of research: 2026-10-25.

**Conventions.** `[S]` = taken from a source I opened or a search result that named the source (URL given). `[calc]` = my own arithmetic from a sourced formula. `[ASSUMPTION]` = illustrative number I chose, NOT a measurement. `[UNVERIFIED]` = came from an aggregator/secondary blog or conflicts between sources. Where I could not find evidence I say so rather than guess.

**Evidence limits (read first).**
- Vendor prices for Anthropic and OpenAI were read from the vendor pricing pages. Gemini 4, Grok 4.7, DeepSeek, Kimi, Qwen and GLM figures come only from aggregators (`ioptera.com/data/llm-prices.csv`, `agentleaderboards.com`) and are `[UNVERIFIED]`. The two aggregators disagree on DeepSeek V4.1 Flash input price ($0.02 vs $0.30 per MTok).
- I found *no* independent long-context benchmark numbers for the very newest models (Opus 5.5, GPT-6.x, Gemini 4). Benchmark evidence below is mostly for the Opus 4.6 / GPT-5.x / Gemini 3.x generation, so "effective context today" is probably better than the numbers shown but I cannot prove it.
- Several 2026 papers I cite (Context Kubernetes, PACMI, CoAgent, ATLAS) are recent preprints from small teams; treat headline numbers as unreplicated.

---

# PART 1 — Current long-context methods and where each fails for massive CONCURRENT workloads

## 1.0 The baseline: what "big context" actually delivers

**Windows and prices (Oct 2026).**
- Anthropic: Claude 4.6+ models (except Haiku 5.5) get the full 1M window at standard price with no long-context premium. Opus 5.5 $4 in / $20 out per MTok; Sonnet 5.5 $2 / $10; Haiku 5.5 $0.10 / $0.50 up to 100K and $0.50 / $2.50 above. Cache read is 0.1x input (Opus 5.5 $0.20, Sonnet 5.5 $0.10); cache write is 1.25x (5 min) or 2x (1 h). Batch gives 50% off. A newer tokenizer yields ~30% more tokens for the same text. `[S]` https://platform.claude.com/docs/en/about-claude/pricing
- OpenAI: short context is ≤272K input tokens, long is >272K and costs more. gpt-6.1-sol $2/$10 short, $4/$15 long, cached $0.10; gpt-6-astra $10/$50 short, $20/$75 long. The ~1.05M window figure is from aggregators `[UNVERIFIED]`. OpenAI says it is winding down self-serve fine-tuning. `[S]` https://developers.openai.com/api/docs/pricing
- Others `[UNVERIFIED]`: Gemini 4 Argon ~1.05M ctx, $2/$10; Grok 4.7 500K; DeepSeek V4.1 Flash, Kimi K3.1 Pro, Mistral Large 4, Qwen3.8 Max, GLM 5.3 all listed at ~1M. https://ioptera.com/data/llm-prices.csv , https://agentleaderboards.com/

**Advertised ≠ effective.**
- *Lost in the Middle*: accuracy is U-shaped in position; GPT-3.5 multi-doc QA fell below its closed-book score (56.1%) when the answer sat mid-context; reader quality saturates before retriever recall does. `[S]` https://arxiv.org/abs/2307.03172
- *RULER*: defines "effective length" as the longest length above a threshold (85.6%); many models fall short of their claimed length. `[S]` https://arxiv.org/abs/2404.06654
- *NoLiMa* (needles with no lexical overlap): at 32K, 11 of 13 models fell below 50% of their short-context baseline; GPT-4.1 (claimed 1M) had effective length 16K; Llama 4 Scout (claimed 10M) about 1K. `[S]` https://arxiv.org/abs/2502.05167 , https://github.com/adobe-research/NoLiMa
- *HELMET*: needle-in-a-haystack does not predict downstream performance; RAG-style tasks are a cheap, predictive proxy. `[S]` https://arxiv.org/abs/2410.02694
- *Chroma "Context Rot"* (Jul 2025): 18 LLMs degrade as input grows even on simple tasks; lower question–needle similarity and distractors degrade faster. `[S]` https://www.trychroma.com/research/context-rot
- *ATLAS* (May 2026): 26 models, 8K–1M. Mean relative decay from 128K to 1M is 24.3%; retrieval and QA decay most (>40%, some 70%+). Opus 4.6 leads at 1M (ATLAScore 70.55, only 8.5% decay); Gemini 3.1 Pro leads at 128K. Reasoning models decay less (correlation only). A full 1M evaluation costs ≈1,711M tokens per model. `[S]` https://arxiv.org/abs/2605.28079
- MRCR v2 8-needle (secondary blog, Mar 2026, mixed eval conditions, not comparable across sources) `[UNVERIFIED]`: Opus 4.6 76% at 1M; Sonnet 4.6 65.8% at 1M; GPT-5.4 36.6% at 512K–1M; Gemini 3 Pro ~25% at 1M. https://yage.ai/share/long-context-benchmark-en-20260315.html
- Takeaway: 1M-token windows are now usable on the best models for lookup-style tasks, but recall/QA still decays with length, and multi-hop/graph-style reasoning is much weaker (GraphWalks BFS ≈40% at 1M per the same blog `[UNVERIFIED]`). Anthropic's own engineering position: "The solution isn't more capacity; it's better management" (as quoted by the yage.ai survey, `[UNVERIFIED]` as a quote).

**Serving cost of long context.**
- KV bytes/token = 2 × layers × KV heads × head_dim × bytes. For Llama-3.1-70B in BF16 this is 320 KiB/token, i.e. ≈43 GB (decimal) for one 128K context and ≈328 GB for 1M `[calc from S]`. Formula/figure: https://docs.min.io/memkv/operate/kv-cache-sizing/ , https://thegustafson.com/blog/memory-management . (The Cartridges paper quotes 84 GB for a 128K Llama-70B context, which does not match my arithmetic; I cannot reconcile it — treat as uncertain.)
- The Cartridges paper measured an H100 serving Llama-8B losing 77x peak throughput going from 1K to 120K-token contexts. `[S]` https://arxiv.org/abs/2506.06266
- PagedAttention removes fragmentation but not the size. https://arxiv.org/abs/2309.06180 . Chunked prefill interleaves prefill with decode to protect latency: https://docs.vllm.ai/en/stable/configuration/optimization/

## 1.1 Method-by-method: what it buys, where it breaks under concurrency

| Method (key sources) | What it solves | Where it falls short for massive concurrent workloads |
|---|---|---|
| **Prompt caching** (vendor pages above) | Cuts repeated-prefix cost to 0.1x and latency | Prefix-only: a change early in a prompt invalidates everything after it. Cache is per-org/per-prefix, TTL-bound (5 min / 1 h), so 10^5 agents with different working contexts mostly miss. Cross-user sharing is a security problem: shared prefix caches leak via timing; audits found global sharing in 7 providers in 2024 and recommend per-user/per-tenant namespaces (https://proceedings.mlr.press/v267/gu25b.html , https://arxiv.org/html/2508.08438v1). So security pushes toward *less* sharing, exactly when concurrency needs *more*. |
| **Hybrid search + reranking, contextual retrieval** (https://www.anthropic.com/engineering/contextual-retrieval) | Contextual embeddings + BM25 cut top-20 retrieval failures 49% (5.7%→2.9%); + reranking 67% (→1.9%) `[S]`. | Retrieval is per-query, per-agent: N agents asking overlapping questions each re-retrieve and re-read the same chunks (duplicated context). Index freshness is eventual: every write must be embedded/indexed before it can be found. Top-k retrieval cannot answer questions whose evidence is spread across many documents or that need aggregation. |
| **Agentic / iterative retrieval** (tool-using search loops) | Lets the model reformulate and follow leads; handles multi-hop better than one-shot RAG. | I did not collect a benchmark for this, so no number here. Structurally: cost and latency scale with number of tool calls × context re-read each step; thousands of agents multiply load on the search backend; every step re-reads a growing history. |
| **GraphRAG / LazyGraphRAG** (https://microsoft.github.io/graphrag/index/methods/ , https://www.microsoft.com/en-us/research/blog/lazygraphrag-setting-a-new-standard-for-quality-and-cost/) | Global/thematic questions via entity graph + community summaries. `graphrag update` supports incremental indexing; LazyGraphRAG's indexing cost equals vector RAG and is 0.1% of full GraphRAG `[S]`. | Full GraphRAG indexing is LLM-heavy; incremental update re-merges entities and recomputes communities, not designed for continuous high-rate writes (my reading of the docs; no write-rate benchmark found). Lazy variant moves cost to query time → concurrency pays it repeatedly. No ACL model in the indexes. |
| **RAPTOR** (recursive cluster-and-summarize tree) https://arxiv.org/abs/2401.18059 | QuALITY 82.6% with GPT-4; good for multi-level questions `[S]`. | Static tree: a changed leaf invalidates ancestor summaries (my inference, not stated by the paper). Summaries are lossy and permission-blind: one summary node mixes documents with different ACLs. |
| **Prompt compression** (LLMLingua https://arxiv.org/abs/2310.05736: up to 20x with ~1.5 pt GSM8K loss; gist tokens https://arxiv.org/abs/2304.08467: up to 26x, 40% FLOPs saving) | Fewer tokens in. | Compresses a *given* context; does not decide *which* context. Lossy in unpredictable ways for exact facts. Per-request compression compute is repeated across agents. The Cartridges paper reports quality drops once compression exceeds ~2x on hard long-context tasks `[S]`. |
| **KV-cache eviction/compression** (H2O https://arxiv.org/abs/2306.14048 ; SnapKV https://arxiv.org/abs/2404.14469: 3.6x faster generation, 8.2x memory at 16K) | Shrinks the per-session cache. | Eviction is query-dependent and irreversible; SnapKV-style selection can bias against some instructions in multi-instruction prompts `[S]`. A cache evicted for one question is wrong for the next, which hurts shared/reused caches. |
| **Sparse / linear attention and hybrids**: DeepSeek Sparse Attention (lightning indexer + top-k=2048; main attention O(L²)→O(Lk); ~50%+ API price cut, quality on par with V3.1-Terminus) https://arxiv.org/abs/2512.02556 ; MoBA https://arxiv.org/abs/2502.13189 ; Kimi Linear (3:1 KDA:MLA) https://arxiv.org/abs/2510.26692 ; Ring-linear https://arxiv.org/abs/2510.19338 | Cheaper compute and memory per token at length. | They cut cost *per session*, not the number of sessions or cross-session redundancy. DSA's indexer is still O(L²) (cheap constant) and keeps its own key cache. Linear-attention models can lose exact recall: Kimi-Linear-48B ranked ~33 at 1M in ATLAS `[S]`. |
| **State-space / RWKV / Mamba hybrids** (Nemotron-H https://research.nvidia.com/labs/adlr/nemotronh/ ; theory of copying limits https://arxiv.org/abs/2402.01032) | Constant-size state, great throughput. | Fixed-size state cannot hold arbitrary exact facts; recent mechanistic work suggests exact retrieval still routes through the few attention layers (https://arxiv.org/html/2609.04434v1 — one search result, not opened) `[UNVERIFIED]`. A single state is also per-sequence, not shareable. |
| **Test-time memory (Titans)** https://arxiv.org/abs/2501.00663 | Neural memory updated at inference; authors report >2M effective context and 95–98% on RULER S-NIAH at 16K. | Author-reported, unreplicated at frontier scale; Cartridges authors note such architectures need training from scratch and "do not match attention on recall-intensive tasks" `[S]` (https://arxiv.org/abs/2506.06266). A per-agent memory is private state: no cross-agent consistency or ACL story. |
| **Agent memory stores** (MemGPT https://arxiv.org/abs/2310.08560 core/recall/archival tiers; Mem0 https://arxiv.org/abs/2504.19413 67.1 single-hop / 51.2 multi-hop / 55.5 temporal on LoCoMo; Letta filesystem agent 74.0% LoCoMo vs Mem0 66.9% — different harnesses, not directly comparable https://www.letta.com/blog/benchmarking-ai-agent-memory/) | Persistence across sessions; self-managed paging. | Designed for one user/one agent. Memory writes are LLM calls (cost per write); multi-hop and temporal remain weak (Mem0 numbers); concurrent agents writing contradictory memories have no consistency protocol. Continuous LLM rewriting of memory degrades it (cited by PACMI as arXiv 2605.12978 — not opened). |
| **Sleep-time compute** (Letta) https://arxiv.org/abs/2504.13171 | Precompute "learned context" offline: ~5x less test-time compute at equal accuracy on Stateful GSM-Symbolic/AIME; shared context cut cost/query 2.5x; on SWE-Features standard test-time compute wins at high budgets `[S]` (via search synthesis). | Evaluated on small synthetic/benchmark settings; no treatment of data that changes while precomputation runs or of permissions. |
| **Fine-tuning / continual learning to absorb a corpus** | Knowledge without context tokens. EMNLP'24 study: RAG consistently beat unsupervised fine-tuning for new facts https://aclanthology.org/2024.emnlp-main.15.pdf `[S]`. SEAL (self-edits + LoRA) can inject knowledge but repeated sequential edits cause forgetting https://arxiv.org/html/2506.10943v2 `[S]`. | Slow to update, forgets, cannot enforce per-user permissions (weights are shared by everyone who uses them), no reliable deletion. Vendors are retreating from self-serve fine-tuning (OpenAI pricing page). |
| **Cartridges (trained KV caches)** https://arxiv.org/abs/2506.06266 , code https://github.com/HazyResearch/cartridges | Match in-context quality with 38.6x less memory and 26.4x higher peak throughput; extend effective context 128K→484K on MTOB; independently trained cartridges can be concatenated and queried together `[S]`. | Training one ICL-quality Cartridge took ~30 min on an 8×H100 node for Llama-8B (unoptimized) `[S]` — far too slow for continuously changing data. Per-corpus artifact with no update or delete story; experiments used 100K–484K-token single corpora, not enterprise scale. |
| **Serving-layer KV reuse**: CacheBlend/LMCache (non-prefix chunk KV reuse with selective recompute; TTFT 2.2–3.3x faster) https://docs.lmcache.ai/getting_started/quickstart/share_kv_cache ; Mooncake https://kvcache-ai.github.io/Mooncake/getting_started/examples/vllm-integration/kv-cache-storage.html ; Block-Attention (independent blocks; 98.7% lower TTFT at 32K, needs block-aware fine-tuning) https://arxiv.org/html/2409.15355v5 ; KVCOMM (cross-agent KV reuse, >70% reuse, up to 7.8x prefill speedup) https://arxiv.org/abs/2510.12872 ; DroidSpeak (cross-LLM KV sharing, up to 4x throughput) https://arxiv.org/abs/2411.02820 ; Hogwild! Inference (workers attend to each other's concurrent KV) https://arxiv.org/abs/2504.06261 | The most relevant line for concurrency: stop recomputing identical text. | Reuse is keyed by *content*, not by *who may see it*; none of these handle permissions. Most gains are shown at tens of agents, not 10^5. Position-independent reuse costs some accuracy (recompute budget). Storage for KV of a whole corpus is impossible at enterprise scale (see Part 2). |
| **Enterprise governance**: Context Kubernetes (declarative manifests, reconciliation loop, freshness states, agent authority ⊂ human authority, TLA+ checked) https://arxiv.org/abs/2604.11623 ; AWS ACL-aware RAG (pre-filter, overfetch, fine-grained authz, live source-of-truth check) https://aws.amazon.com/blogs/machine-learning/rethinking-access-control-for-rag-with-amazon-quick-and-amazon-bedrock/ ; ACL hydration https://robotics.ee/2026/04/23/introducing-acl-hydration-secure-knowledge-workflows-for-agentic-ai/ | Correct framing of the control plane problem. | Context Kubernetes is a single-author prototype on synthetic data (200 queries; 50 concurrent agents at 6.6 qps, 151 ms) with ACL-filtered RAG showing zero leaks but 82.8% noise `[S]`; no production deployment. Filter-after-retrieval wastes retrieval budget and leaves derived artifacts (summaries, caches) unprotected. |
| **Concurrency/consistency for agents (new in 2026)**: CoAgent/MTPO https://arxiv.org/abs/2606.15376 ; PACMI (provenance-aware cascading invalidation) https://arxiv.org/abs/2610.05732 | CoAgent: notify-and-repair instead of lock/abort; within 5% of serial correctness at 1.4x speedup on 10 contended workloads; 2PL deadlocks 0.81/trial, OCC aborts 0.95/trial at 1.83x token cost `[S]`. PACMI: 0.99 vs 0.90 final accuracy on a stale-memory benchmark `[S]`. | CoAgent needs declared tool footprints ("latent object schema"), tested with two-agent pairs. PACMI's dependency edges were *given by annotation*; benchmark has 6 memories per case; its own cascade ablation was not statistically significant (p=0.057) `[S]`. Neither handles semantic (non-declared) read sets at enterprise scale. |

## 1.2 Cross-cutting shortfalls for concurrent, changing, multi-tenant workloads

1. **Every method optimizes one agent's one prompt.** Cost shows up as (agents × steps × context). Nothing in the list amortizes work *across* agents except serving-layer KV reuse, which ignores permissions.
2. **Freshness is an afterthought.** RAG indexes are eventually consistent; RAPTOR/GraphRAG summaries go stale; agent memories hold superseded facts. Only PACMI-style provenance and CoAgent-style notification address it, and only in small tests.
3. **Cross-document reasoning is the unsolved piece.** Retrieval returns chunks; graphs/summaries precompute some structure but are expensive to update; long-context models decay on multi-hop at length (ATLAS, GraphWalks).
4. **Permissions are enforced at the edge (filter results), not inside shared computation.** Any shared artifact — cache, summary, cartridge, fine-tuned weight — is a potential leak path.
5. **Write rate vs. cost of "understanding" a write.** Embedding is cheap; LLM-derived structure (graph, summary, memory, cartridge) is 3–6 orders of magnitude costlier per write (qualitative; I have only the Cartridges ~30 min/8×H100 and GraphRAG "LLM-heavy" datapoints).

---

# PART 2 — The Amazon-style problem, framed concretely

**What is sourced.** Amazon's 2025 Form 10-K reports ~1,576,000 full- and part-time employees at 31 Dec 2025, plus contractors and temporary staff (search-reported from https://www.sec.gov/Archives/edgar/data/1018724/000101872426000004/amzn-20251231.htm ; I did not open the filing myself). Gartner is cited (inside the Context Kubernetes paper) as predicting >40% of agentic AI projects will be cancelled by 2027 `[S, secondhand]`. Everything else in this part is an `[ASSUMPTION]` chosen to show orders of magnitude, not a claim about Amazon.

**Illustrative assumptions (not measurements).**
- A1: 10^5 AI agents active at once, each acting for a human or a team, each making ~1 model call per minute.
- A2: Enterprise corpus of 10^10 text chunks (tickets, code, docs, logs, chats, dashboards) with 10^5–10^6 chunk writes per second at peak.
- A3: Typical working context per call 200K tokens; some calls 1M.
- A4: Permissions via group membership and per-resource ACLs; a user belongs to dozens of groups, and the ACL set on a resource changes daily.

**Back-of-envelope consequences `[calc from assumptions + sourced prices/formula]`.**
- *Token bill.* 10^5 agents × 60 calls/h × 200K tokens = 1.2×10^12 tokens/h = 1.2M MTok/h. At the sourced Sonnet 5.5 cached rate ($0.10/MTok) that is $120K per hour; uncached ($2/MTok) $2.4M per hour. The point is the *shape*: re-reading context each step is the dominant cost, and caching only helps for exact-prefix repeats.
- *KV memory.* One 128K-context session on a Llama-70B-class GQA model ≈43 GB of KV (calc from the sourced 320 KiB/token). 10^4 simultaneous such sessions ≈ 430 TB of HBM-class memory; even 1% of that is far beyond one cluster node. (Frontier closed models may use smaller KV per token; I have no sourced figure for them.)
- *KV for the corpus.* Storing KV for 10^10 chunks × ~500 tokens at 320 KiB/token would be ~1.6×10^18 bytes (~1.6 EB). Impractical to keep on GPU/NVMe tiers for every agent-facing artifact — so KV-level sharing can only cover a hot working set, not the corpus. Text/derived-artifact-level sharing must carry the cold majority.
- *Freshness window.* If the indexer lags writes by T seconds, then at A2's write rate roughly 10^5·T chunks are invisible or stale at any moment. For T = 60 s that is ~6×10^6 chunks (assumption-driven).

**Failure modes, concretely.**
1. **Stale index.** An agent plans a launch from a ticket that was reassigned 40 seconds ago; vector index and cached summaries still show the old owner. Retrieval returns it with a high similarity score; similarity does not encode validity (PACMI makes this point: a stale memory "may remain highly relevant and still be retrieved" `[S]`).
2. **Retrieval misses cross-document reasoning.** The answer is "supplier X's delay (doc 1) + inventory policy (doc 2) + a promotion calendar (doc 3) ⇒ risk". No single chunk is similar to the question; top-k retrieval returns none of the three together. Long context would hold all three but decays on multi-hop at length; GraphRAG could link them but is costly to keep current.
3. **Agents duplicating context.** 5,000 agents reasoning about the same incident each retrieve and re-read the same runbook, dashboards and chat history; each pays the full prefill and holds its own KV copy. No agent knows another already derived "root cause = config push at 14:02".
4. **KV-cache blow-up.** See arithmetic: memory scales with (sessions × context), and throughput collapses with context length (77x drop for 1K→120K in the Cartridges H100 measurement `[S]`). Prefix caches miss because working contexts diverge after the first few thousand tokens.
5. **Coordination across thousands of simultaneous agents.** Classical 2PL/OCC either deadlock or abort-and-redo minutes of LLM work (CoAgent measurements `[S]`). Agents act on views that were true when read; two agents repair/act on the same resource from different snapshots (CoAgent's canary-on-a-bad-image anomaly `[S]`). No existing system gives a consistency contract at 10^5-agent scale.
6. **Access control.** Agent authority must be a subset of its principal's; but derived content (summaries, shared KV, learned memory, trained cartridges) silently merges documents with different ACLs. Post-retrieval filtering handles raw chunks but not derived artifacts; shared caches leak through timing (Gu et al.; per-tenant namespaces are the recommended mitigation, which defeats sharing). Revocation must take effect immediately; cached artifacts outlive the revocation.
7. **Effective-context illusion.** Even if 1M tokens fit, ATLAS shows retrieval/QA accuracy decays >40% from 128K to 1M for the average model; "put everything in context" is not a strategy at corpus scale (10^10 chunks ≈ 10^12–10^13 tokens, i.e. 10^6–10^7 times a 1M window `[calc from A2, ~500 tokens/chunk]`).

**What "efficient" would need to mean (requirements I derive from the above).**
(a) Work derived from a write is done once and shared by all principals entitled to it; (b) a write invalidates exactly what depended on it, in time proportional to affected items; (c) agents see consistent snapshots or are told precisely what changed; (d) sharing never crosses a permission boundary; (e) per-agent marginal cost ≈ its private delta, not the whole context.

---

# PART 3 — Four new core-level ideas

**Method.** I searched for the nearest prior work for each idea. Several of my first-draft ideas turned out to have close 2026 neighbours (PACMI for provenance invalidation; CoAgent for agent concurrency control). I kept those only where I could name a concrete, defensible difference, and flagged the overlap. I did not do an exhaustive literature review; "I found no paper that…" means *my searches* found none.

## Idea 1 — Label-Lattice Memoization: permission-indexed sharing of every derived artifact, computed on write

**Core insight.** In an enterprise the thing that stops agents sharing computed context is not compute — it is authorization. Treat every reusable artifact (KV segment, summary, derived claim, cartridge) as a value with a *security label* = the set of source ACLs it was computed from. Compute artifacts once per (content-version, label), and let any principal whose entitlements cover the label reuse it (lattice dominance). Do the computation eagerly on write, so cache state is a function of the data, not of who asked — removing the "was this prefix cached by someone else" timing channel by construction.

**Mechanics.**
- *ACL signatures.* Hash each principal's effective group set to a signature id; hash each document's ACL to a label. Distinct signatures should be far fewer than users (hypothesis to test).
- *Artifact store* keyed by (chunk-hash, version, label). Tiers: **hot** = KV segments for the working set, encoded as independent position-independent blocks (Block-Attention / CacheBlend style, with a recompute budget); **warm** = text-derived artifacts (chunk summaries, extracted claims, embeddings); **cold** = raw text only. KV is never stored for the whole corpus (Part 2 arithmetic).
- *Composition.* An agent's context is assembled from artifacts whose label ⊆ the principal's entitlements. A derived artifact's label = the *intersection of audiences* of its inputs (only people who can read every input may read the output).
- *Declassification by re-derivation.* To produce a broadly shareable summary of a mixed-label cluster, re-derive it from only the broadly visible subset and store that as a separate artifact with its own lineage — never "redact" a restricted summary.
- *Revocation.* Labels are versioned; every artifact read checks a monotonically increasing ACL epoch (a lease); on ACL change, the label index is updated and affected artifacts are tombstoned.
- *Serving.* One shared read-only KV copy per (label, version) in paged GPU/CPU/NVMe tiers (Mooncake/LMCache-style storage); per-agent private tail only.

**Why it fixes concurrent scale.** It attacks duplication (3), KV blow-up (4) and access control (6) at once: the unit of sharing becomes the label, not the user. Eager-on-write computation makes freshness a pipeline property and removes behaviour-dependent cache timing. Per-agent marginal memory ≈ private delta.

**Closest prior work and difference.** (i) *Cache-isolation work* (Gu et al., https://proceedings.mlr.press/v267/gu25b.html ; selective KV sharing, https://arxiv.org/html/2508.08438v1) responds to leaks by isolating per tenant/user — the opposite direction; mine maximizes safe sharing. (ii) *FIDES / information-flow control for agents* (https://arxiv.org/html/2505.23643v2) labels data and propagates restrictive labels through tool calls but does not address cached/derived-artifact reuse across principals. (iii) *Context Kubernetes / AWS ACL RAG* filter retrieved chunks, not derived artifacts. (iv) Denning's lattice model of information flow (1976) and Bell–LaPadula are the classical origin of dominance reuse — **this idea is that classical machinery applied to KV/summary caches; the novelty is the application and the compute-on-write design, not the lattice.** I found no paper combining these; my search was not exhaustive.

**What would make it fail.**
- Signature explosion: if ACLs are mostly per-document and individual, there are ~as many labels as users and sharing collapses (decisive empirical question).
- Intersection labels make most derived artifacts so restricted that they are reusable by almost nobody.
- Position-independent KV composition loses accuracy on cross-block reasoning (Block-Attention needs fine-tuning; CacheBlend recomputes).
- Eager computing of every write may cost more than lazy on-demand (many chunks never read).
- Revocation lag creates a window of illegitimate access if leases are too long.
- Covert channels (content-based dedup, artifact-size side channels).
- (Second-pass reviewer note, from an LLM critique I ran; plausible, untested) Labels baked in at compute time go stale when group membership changes; eager computation does not remove all side channels, since artifact existence/size can itself be an oracle for anyone allowed to probe it. Add a revocation test to Stage A: write a restricted doc, derive an artifact, revoke access, and confirm the artifact is refused within the lease window.

**Cheap experiment (no GPU for stage A).**
- *Stage A (1–2 days, CPU):* build a synthetic org (e.g., 10^4 users, Zipf-distributed group sizes, documents with ACLs drawn from groups; vary the fraction of per-user-private docs). Replay a synthetic read log. Measure: number of distinct signatures; fraction of read-mass servable from shared artifacts vs. a per-user cache; storage ratio. Falsifier: if ≥50% of read-mass requires labels with ≤3 principals, drop the idea. Then repeat with real ACL exports if any is available to you (e.g., a Google Drive/GitHub org you can export — permissions only, no content).
- *Stage B (GPU, small model):* encode 200 documents as independent blocks; compare answer accuracy on cross-document questions for (a) full-context prefill, (b) independent-block KV + 10% recompute, (c) RAG; confirm label filtering does not change accuracy beyond the removed documents.

**Feasibility.** Stage A: high. Full system: medium (engineering-heavy, mostly systems work; model-side work limited to block-KV quality).

## Idea 2 — Context Percolator: invert the index; push deltas to subscribed agents as append-only KV patches

**Core insight.** RAG does O(agents × steps) lookups against O(corpus). With a high write rate and many long-lived agents, flip it: index the *agents' standing interests* and route each write to the agents it affects. Cost per write is a nearest-neighbour search over subscriptions (~10^5–10^6 vectors) instead of every agent re-querying a 10^10-chunk index every step. Then deliver changes in a form that keeps the agent's prefix KV cache valid: append a "delta record" to the context instead of rewriting earlier text.

**Mechanics.**
- *Subscriptions:* each agent has a few standing-query embeddings plus a symbolic filter (resource ids, labels) derived from its task and from what it has actually used (relevance feedback: chunks it cited strengthen the subscription; ignored deliveries decay it).
- *Write path:* new/changed chunk → embed once → ANN search over subscription index → candidate agents → cheap cross-encoder or small-LLM relevance gate → ACL check against the artifact label (Idea 1) → enqueue.
- *Delivery format:* append-only "patch" messages (`[Δ t=…: doc D v7 supersedes v6: <diff>]`); the earlier context and its prefix cache stay untouched. A periodic *compaction epoch* rewrites the context (dropping superseded text) and pays one prefill; an agent can request compaction early.
- *Coalescing:* multiple agents with overlapping subscriptions receive the same patch text → patch KV computed once and shared (position-independent block encoding, as in Idea 1).
- *Backpressure:* per-agent patch budget; if exceeded, deliver a digest and flag "context drifted — compact".

**Why it fixes concurrent scale.** Retrieval load stops scaling with agents × steps; staleness becomes "time until a patch is delivered" (bounded and measurable); duplicate reading is replaced by one shared patch; prefix caches survive updates.

**Closest prior work and difference.** *Selective dissemination of information / standing queries* (decades old) and Elasticsearch's percolator (reverse search) are the IR/database origin — **this is an application of that pattern; I flag the overlap.** CoAgent (https://arxiv.org/abs/2606.15376) already pushes one-way notifications to agents whose *declared tool footprints* a write touches; my difference is semantic, learned subscriptions over unstructured enterprise content, and a KV-prefix-preserving patch format with compaction. MemGPT/Letta (https://arxiv.org/abs/2310.08560) pull memory by agent decision; sleep-time compute (https://arxiv.org/abs/2504.13171) precomputes offline but does not route changes to agents.

**What would make it fail.**
- Low precision: agents are flooded with irrelevant patches (context pollution and context rot, per Chroma/ATLAS).
- Low recall: an agent relies on a change it never subscribed to (silent staleness) — subscriptions are only as good as the agent's own task model.
- Patch accumulation degrades answers before compaction; compaction cost × agents could erase the savings.
- Append-only patches make the model attend to contradictory old and new text; models may prefer the earlier, longer text.
- (Reviewer note) False negatives are invisible, unlike cache misses. Add to the experiment: build ~100 ground-truth should-notify pairs and report recall of cosine-threshold routing against them before anything else.

**Cheap experiment.** Simulate a document stream with edits (a synthetic wiki, ~2,000 docs, 10% edited per simulated hour) and 200 simulated agents each with a task and 20 questions whose answers change when docs change. Compare: (a) pull-RAG re-retrieving every question; (b) percolator push + patches; (c) both. Metrics: stale-answer rate, tokens read per answer, patches delivered per agent, answer accuracy. Can be done with a small open model/API and no training. Falsifier: push precision <30% at recall ≥90%, or no token saving over (a).

**Feasibility.** High for a prototype (mostly existing components); medium to make precision/recall good with learned subscriptions.

## Idea 3 — Log-structured parametric memory (LSM of Cartridges) with in-context tombstones

**Core insight.** A trained KV cache (Cartridge) is a 26x-throughput, 38.6x-smaller way to give hundreds of thousands of agents the same corpus knowledge — but retraining per edit takes ~30 min on 8×H100. Databases solved "slow-to-rebuild big structure + fast writes" with log-structured merge trees. Do the same for parametric memory: a large immutable *base cartridge*, small *delta cartridges* for recent changes, fresh text in context (L0), and background *compaction by context distillation*; deletions/overrides are handled by tombstones carried in the context, which always win.

**Mechanics.**
- Level 0: recent writes as text (served by RAG/Idea 2 patches). Level 1: delta cartridges (small p, trained quickly on synthetic conversations about only the changed text, initialized from the KV of that text, as in the Cartridges recipe). Level 2: base cartridge per domain/label.
- Serving concatenates [base ‖ deltas ‖ tombstone block ‖ L0 text ‖ query] — composition without retraining is reported to work in the Cartridges paper `[S]`.
- Compaction: periodically distil the *composed* model (base + deltas + L0) into a new base cartridge (teacher = model with composed state in context, the same distillation objective). Tombstones are dropped only after the new base provably (by held-out probes) no longer asserts the superseded fact.
- One cartridge family per security label (Idea 1) so parameters never mix ACLs.

**Why it fixes concurrent scale.** Reads are shared read-only caches (large memory/throughput gain per Cartridges numbers); writes are O(delta); staleness is bounded by tombstones; the cold bulk of knowledge costs almost no per-agent context.

**Closest prior work and difference.** *Cartridges* (https://arxiv.org/abs/2506.06266) — static per-corpus; no update/delete story. *Parametric RAG* (Su et al., https://arxiv.org/abs/2501.15915, described in the Cartridges appendix) trains a LoRA per document and merges retrieved ones at inference; mine uses KV-prefix artifacts, hierarchical LSM levels, tombstones and compaction. *SEAL* (https://arxiv.org/html/2506.10943v2) updates one set of weights and forgets. LSM-tree (O'Neil et al. 1996) is the database origin — **flagged: the structure is borrowed.**

**What would make it fail.**
- Delta training too slow/expensive for realistic write rates; L0 then carries everything and nothing is saved.
- Composition interference grows with the number of deltas (the paper tested only pairs of 10-K cartridges `[S]`).
- Parametric artifacts cannot reliably forget; a tombstone-in-context may be ignored by the model (context vs. weights conflict).
- Compaction distillation drifts (each generation loses detail).
- Evidence for knowledge injection vs. RAG is mixed (EMNLP'24 favours RAG for new facts).
- (Reviewer note) Unlike LSM merges, which are exact, distillation compaction is lossy and has no correctness invariant; measure a fixed fact-probe set before and after each compaction pass.

**Cheap experiment.** Use the HazyResearch/cartridges code with a small model (Llama-3B/8B class, as in the paper). Take two ~50K-token documents; edit 20 facts. Compare accuracy on edited and unedited facts, and wall-clock training time, for: (a) retrain full cartridge, (b) base + delta cartridge, (c) base + edited text in context, (d) base + tombstone note. Falsifier: (b)/(d) lose >10 points vs (a) or delta training time is not ≥10x cheaper than full retrain.

**Feasibility.** Low–medium (research risk is high; engineering is moderate). Most dependent on a faster cartridge-training recipe.

## Idea 4 — Faithful premise ledgers: make an agent's read-set explicit and trainable, so invalidation can be targeted

**Core insight.** PACMI-style invalidation needs dependency edges (given by annotation in its benchmark, which its authors flag as an unsolved problem), and CoAgent needs declared tool footprints (its "latent object schema assumption"). Real agents carry premises in free text. If each agent must emit a compact *premise ledger* — (source id, version/hash, claim, which action depends on it) — before each consequential action, then a write can be matched to the ledgers it breaks with an inverted index (premise → agents), and only those agents are notified. The hard part is making the ledger *faithful*; train that with counterfactual replay.

**Mechanics.**
- *Ledger format:* structured entries appended to the agent's context and stored in a shared ledger service, indexed by source id/version.
- *Training/inference for faithfulness:* sample past trajectories; for each action, perturb (stale-ify) (i) a ledgered premise and (ii) a random unledgered span. Reward ledgers where perturbing a listed premise changes the action and perturbing an unlisted span does not. Use this as an RL reward or as a rejection-sampling filter for supervised fine-tuning.
- *Runtime:* write event → ledger index → affected agents get a CoAgent-style notification with old/new value; the agent patches only dependent actions. Identical ledger entries across agents reveal duplicated reasoning that can be shared (links to Idea 2).
- *Audit mode:* a cheap probabilistic check re-runs a sampled fraction of actions with perturbed premises to estimate ledger recall online.

**Why it fixes concurrent scale.** Invalidation and coordination cost scales with the *number of affected agents*, not all agents; no locking; targeted repair avoids whole-task aborts (the OCC 1.83x token-cost problem measured by CoAgent `[S]`).

**Closest prior work and difference.** *CoAgent/MTPO* (https://arxiv.org/abs/2606.15376): requires declared footprints and was tested on agent pairs; mine targets context-carried premises. *PACMI* (https://arxiv.org/abs/2610.05732): provenance edges assumed; mine learns to produce them. *S-Bus* (https://arxiv.org/abs/2605.17076, as described in CoAgent's related work): reconstructs read sets from HTTP traffic and reportedly misses 74% of reads on SWE-bench (reported secondhand, `[UNVERIFIED]`). The overlap with chain-of-thought faithfulness research is real: self-reported reasoning is known to be unreliable, which is precisely this idea's main risk.

**What would make it fail.**
- Unfaithful ledgers: models under-report (silent staleness) or over-report (notification storms, abort-like churn).
- Counterfactual-perturbation reward is noisy and may be gamed.
- Ledger overhead per action may exceed the invalidation savings for short tasks.
- Semantic matching between a changed document and a ledger entry can miss indirect dependencies (the premise "inventory is fine" depends on many sources).
- (Reviewer note) Correct invalidation presupposes the causal dependency graph, which is the unsolved part; under-invalidation gives silent staleness and over-invalidation gives cascading storms. Test with an injected multi-hop dependency chain and report the miss rate.

**Cheap experiment.** Re-create a CoAgent-style canary scenario family (two agents, a shared state with an injected change) as 50 episodes with a stale-value injection; use *prompting only* (no training) to elicit ledgers; measure ledger recall = fraction of episodes where perturbing an unledgered premise changes the action, and precision of notifications. Falsifier: recall <80% with a frontier model and a straightforward prompt — then training is unlikely to be worth it.

**Feasibility.** Medium (prompting version is cheap; RL part is expensive and uncertain).

## Single best bet: Idea 1 (Label-Lattice Memoization)

**Why.**
1. It targets the constraint unique to big enterprises — permissions — which blocks every cross-agent efficiency trick (shared KV, shared summaries, shared memory). Ideas 2–4 all need an answer to "may this agent see this artifact?" and Idea 1 is that layer.
2. Two of the other ideas have strong 2026 neighbours (CoAgent, PACMI) and one depends on a training recipe that does not exist yet (fast Cartridges). The permission-aware sharing of *derived* artifacts is the space where I found no direct competitor (not exhaustive).
3. It is cheaply falsifiable: Stage A is a CPU simulation of ACL-signature counts and shareable read-mass; if real-world permission structure does not collapse into few labels, the idea dies in days at near-zero cost.
4. It composes with the others: Idea 2's patches and Idea 3's cartridges become per-label artifacts; Idea 4's ledgers can reference artifact (hash, version, label) triples.

**Honest risk.** The core machinery is classical (information-flow lattices, memoization); the contribution would be showing it *works at the KV/derived-artifact level with acceptable accuracy loss*, and that real enterprise ACLs are shareable enough. If signatures explode, fall back to Idea 2 as the best bet.

---

## Reference list (supports Parts 1–3; all URLs as cited above)

Pricing/vendors: https://platform.claude.com/docs/en/about-claude/pricing ; https://developers.openai.com/api/docs/pricing ; https://ioptera.com/data/llm-prices.csv ; https://agentleaderboards.com/
Benchmarks: https://arxiv.org/abs/2307.03172 ; https://arxiv.org/abs/2404.06654 ; https://arxiv.org/abs/2502.05167 ; https://arxiv.org/abs/2410.02694 ; https://www.trychroma.com/research/context-rot ; https://arxiv.org/abs/2605.28079 ; https://yage.ai/share/long-context-benchmark-en-20260315.html
Architectures/attention: https://arxiv.org/abs/2512.02556 ; https://github.com/deepseek-ai/DeepSeek-V3.2-Exp/ ; https://arxiv.org/abs/2502.13189 ; https://arxiv.org/abs/2510.26692 ; https://arxiv.org/abs/2510.19338 ; https://arxiv.org/abs/2510.04800 ; https://arxiv.org/abs/2402.01032 ; https://research.nvidia.com/labs/adlr/nemotronh/ ; https://arxiv.org/abs/2501.00663
Retrieval/summarization: https://www.anthropic.com/engineering/contextual-retrieval ; https://microsoft.github.io/graphrag/index/methods/ ; https://www.microsoft.com/en-us/research/blog/lazygraphrag-setting-a-new-standard-for-quality-and-cost/ ; https://arxiv.org/abs/2401.18059
Compression: https://arxiv.org/abs/2310.05736 ; https://arxiv.org/abs/2304.08467 ; https://arxiv.org/abs/2306.14048 ; https://arxiv.org/abs/2404.14469 ; https://arxiv.org/abs/2506.06266 ; https://github.com/HazyResearch/cartridges ; https://arxiv.org/abs/2501.15915
Memory: https://arxiv.org/abs/2310.08560 ; https://arxiv.org/abs/2504.19413 ; https://www.letta.com/blog/benchmarking-ai-agent-memory/ ; https://arxiv.org/abs/2504.13171 ; https://aclanthology.org/2024.emnlp-main.15.pdf ; https://arxiv.org/html/2506.10943v2
Serving: https://arxiv.org/abs/2309.06180 ; https://docs.vllm.ai/en/stable/configuration/optimization/ ; https://docs.min.io/memkv/operate/kv-cache-sizing/ ; https://thegustafson.com/blog/memory-management ; https://docs.lmcache.ai/getting_started/quickstart/share_kv_cache ; https://kvcache-ai.github.io/Mooncake/getting_started/examples/vllm-integration/kv-cache-storage.html ; https://arxiv.org/abs/2510.12872 ; https://arxiv.org/abs/2411.02820 ; https://arxiv.org/abs/2504.06261 ; https://arxiv.org/html/2409.15355v5
Enterprise/security/concurrency: https://arxiv.org/abs/2604.11623 ; https://aws.amazon.com/blogs/machine-learning/rethinking-access-control-for-rag-with-amazon-quick-and-amazon-bedrock/ ; https://robotics.ee/2026/04/23/introducing-acl-hydration-secure-knowledge-workflows-for-agentic-ai/ ; https://proceedings.mlr.press/v267/gu25b.html ; https://arxiv.org/html/2508.08438v1 ; https://arxiv.org/html/2505.23643v2 ; https://arxiv.org/abs/2606.15376 ; https://arxiv.org/abs/2610.05732 ; https://www.sec.gov/Archives/edgar/data/1018724/000101872426000004/amzn-20251231.htm
Classical references named without links (from memory, not re-verified): Denning 1976 lattice model of secure information flow; Bell–LaPadula; O'Neil et al. 1996 LSM-tree; Doyle 1979 truth maintenance (cited inside PACMI).
