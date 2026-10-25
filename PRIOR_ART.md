# Prior art for "label-lattice memoization"

Prepared 2026-10-25 (America/Toronto). Method: WebSearch plus opening primary pages (arXiv abstracts or HTML, GitHub README/API, vendor docs) with curl or WebFetch. This is a best-effort search, not exhaustive.

**Idea under test** (from docs/long-context-research.md, Idea 1): every reusable derived artifact (KV segments, summaries, claims, embeddings, cartridges) carries a security label = intersection of source ACLs. Artifacts are computed once per (content-version, label) and reused by any principal whose entitlements dominate the label. Compute is eager on write. Declassification is by re-derivation. Revocation uses versioned labels or epoch leases.

**Aspect key** (columns): A = labels on derived artifacts; B = cross-principal sharing by dominance; C = compute-on-write (eager); D = declassification by re-derivation; E = revocation epochs/leases; L = level (KV = KV-level, TXT = text/answer/memory-level, IFC = agent dataflow, none).
Symbols: Y = yes, p = partial, n = no, ? = not verified.
**Verification:** [O] = I opened the primary source. [S] = search-result summary only, so lower confidence.
**Closeness 0-5** is closeness to the WHOLE idea, not to one aspect.

## Table

| # | Name | Type, date | URL | What it does | A | B | C | D | E | L | Close | Ver |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 1 | **AkasicMEM** (GraphAI) | paper, arXiv 22 Sep 2026 | https://arxiv.org/abs/2609.25563 | Governed enterprise agent memory. Effective auth A(m) = R(m) ∩ ⋂ R(ancestors) via transitive lineage; a memory is served iff the principal ∈ A(m). Policy is composed at formation and re-evaluated at retrieval. Declassification = recorded exclusion of an ancestor, gated by an NLI test or a human reviewer. Lazy staleness flags, explicitly rejecting eager propagation. | Y | Y (membership, not lattice) | n (explicitly lazy) | p (exclusion, not re-derivation) | p (stale flags, no epochs) | TXT | **4** | O |
| 2 | **hectar-glitches/tessera** (hackathon demo) | GitHub, created 2026-06-21, last push 2026-09-20, 0 stars | https://github.com/hectar-glitches/tessera | Semantic-cache RAG. Per-section ACL (ordered level public<employee<manager<exec, plus unordered team). A cached answer "inherits the most-restrictive label" of source chunks; hit iff level ≥ entry.level and team matches. Chunk-hash reverse index, sensitivity-tiered TTLs. | Y | Y (level dominance + team) | n | n | p (reverse-index invalidation, TTL) | TXT | **3** | O |
| 3 | **Tessera: Demand-Driven KV Cache Mgmt for RAG LLM Serving** (UCSC) | paper, arXiv 2609.32999, Sep 2026 | https://arxiv.org/abs/2609.32999 | Composable per-context-unit KV reuse (EPIC-style), shared RDMA pool, pending→ready publication with storage epochs and read leases. Discussion sketches ACL namespaces, authorization before KV resolution, and revocation (invalidate shared/local entries, reject stale writeback, fence accesses). It leaves online revocation out of scope. | p (sketch) | p (scope namespaces) | n (demand-driven) | n | p (epochs are for allocation safety, not ACL) | **KV** | **3** | O |
| 4 | **Preserving Provenance in Shared KV Caches** ("provenance-blind reuse") | paper, arXiv 2609.38706, Sep 2026 | https://arxiv.org/abs/2609.38706 | Shows LMCache, Mooncake, HiCache and the vLLM FS connector omit cache_salt/adapter/version from shared-tier keys. Cross-instance timing attack reaches 93% accuracy. Proposes a "KV provenance contract" with the invariant ¬ShareAllowed ⇒ key differs. | p | p (binary/equivalence class) | n | n | n | **KV** | **3** | O |
| 5 | **FIDES** (Microsoft) "Securing AI Agents with IFC" | paper, arXiv 2505.23643, 2025 | https://arxiv.org/html/2505.23643v2 | Confidentiality lattice (readers powerset, join = intersection). Derived data takes the join of its inputs. Quarantined LLM, constrained outputs, declassification/endorsement hatches. No caching. | Y | n (no reuse) | n | p (declassify hatches) | n | IFC | **3** | O |
| 6 | **Zep / Graphiti provenance** | vendor blog + docs, date not seen | https://www.getzep.com/blog/how-zep-tracks-provenance-in-agent-memory/ | Raw episodes are linked to derived entities and facts. Episode metadata is projected onto derived artifacts as a deduplicated union of source tags for ABAC filtering. Deleting an episode cascades to facts supported only by it. | p (tags) | p | n | n | p (delete cascade) | TXT | **2** | S |
| 7 | CachePrune | paper, arXiv 2605.23640, May 2026 | https://arxiv.org/abs/2605.23640 | Token-level sensitivity mask excludes sensitive tokens from cross-user KV reuse. Binary mask, no lattice, no revocation. | p | p | n | n | n | KV | 2 | O |
| 8 | SafeKV / Selective KV-Cache Sharing | paper, arXiv 2508.08438, Aug 2025 | https://arxiv.org/html/2508.08438 | Privacy classifier plus radix-tree manager; shares only non-sensitive blocks; up to 2.66× throughput vs full isolation. | p | p | n | n | n | KV | 2 | O |
| 9 | CacheSolidarity (arXiv title; a later paper cites the same ID as "PrefixWall", possible rename, unresolved) | paper, arXiv 2603.10726, Mar 2026 | https://arxiv.org/abs/2603.10726 | Detects suspicious cross-user prefix reuse and isolates only those entries. OwnerID metadata. Detection-based, not label-based. | n | p | n | n | n | KV | 2 | O |
| 10 | KVGov | paper, arXiv 2608.09225, Aug 2026 | https://arxiv.org/abs/2608.09225 | Per-principal HMAC salt seeds the block-hash chain, giving disjoint caches (isolation, the opposite of dominance sharing). PII admission gate. Mostly simulation. | n | n | n | n | n | KV | 2 | O |
| 11 | BIO-MemArt | paper, arXiv 2609.08566, 8 Sep 2026 | https://arxiv.org/abs/2609.08566 | Attaches a biometric template to each stored KV memory block and filters the shared pool per user before KV reuse. Binary owner gating. | p | n (owner only) | n | n | n | KV | 2 | O |
| 12 | Context Kubernetes | paper, arXiv 2604.11623, 13 Apr 2026; repo Cohorte-ai/context-kubernetes | https://arxiv.org/abs/2604.11623 | Agent permissions ⊆ user's; ACL-filtered retrieval; freshness reconcile loop; TLA+. No derived-artifact labels or caches. | n | n | n | n | p (freshness) | none | 2 | O (abstract) |
| 13 | Practitioner guidance: RAG cache vs revocation. De Vos (18 Oct 2026); Ampity; cloudsecuritydesk (undated) | blogs | https://thomasdevos.com/posts/rag-cache-permission-revocation/ ; https://ampity.io/insights/blog/rag-access-revocation-cache ; https://cloudsecuritydesk.com/publications/semantic-cache-authorization-scope | Bind cached answers to tenant + principal or entitlement-set hash + a monotonic **authorization epoch** + a **dependency manifest** of source docs. Re-check on every hit and fail closed. Exact-equality partitions, not dominance. | p (manifest) | n (exact partition) | n | n | **Y (epoch, lease noted)** | TXT | 2 | O |
| 14 | PACMI | paper, arXiv 2610.05732, 5 Oct 2026 | https://arxiv.org/abs/2610.05732 | Provenance-aware cascading invalidation for agent memory. Typed provenance graph, validity states. No security labels seen. | n | n | n | n | p (invalidation, not security) | TXT | 1 | S |
| 15 | Microsoft Agent Control Spec / agent-governance-toolkit IFC | docs, date not seen | https://github.com/microsoft/agent-governance-toolkit/blob/main/policy-engine/docs/ifc-label-flow.md | Derived data gets the LUB label; clearance dominance check; labels persisted by the host across turns. No cache. | Y | n | n | n | n | IFC | 2 | O |
| 16 | Microsoft 365 Copilot semantic index | vendor docs | https://learn.microsoft.com/en-us/MicrosoftSearch/semantic-index-for-copilot | Grounding is permission-trimmed per user at query time. Claim that generated summaries inherit sensitivity labels was NOT confirmed on the page I opened. | ? | n | n | n | n | TXT | 1 | partly S |
| 17 | Glean | vendor docs | https://docs.glean.com/security/security-principles ; https://developers.glean.com/libraries/indexing-sdk/permissions | Per-doc ACLs (allowed_users/groups/group_intersections), enforced at query time for search, answers and agents. | n | n | n | n | n | TXT | 1 | S |
| 18 | AWS Bedrock KB ACL / Kendra user-context | vendor docs | https://docs.aws.amazon.com/bedrock/latest/userguide/kb-managed-acl.html | Retrieve with userContext; deny overrides allow; query-time filtering. | n | n | n | n | n | TXT | 1 | S |
| 19 | Google Agentspace; Atlassian Rovo | vendor docs | https://cloud.google.com/agentspace/agentspace-enterprise/docs/identity ; https://support.atlassian.com/rovo/docs/rovo-agent-permissions-and-governance/ | The calling user's source permissions are enforced on retrieval; agents act as the user. | n | n | n | n | n | TXT | 1 | S |
| 20 | Anthropic / OpenAI prompt caching | vendor docs | https://platform.claude.com/docs/en/build-with-claude/prompt-caching ; https://developers.openai.com/api/docs/guides/prompt-caching | Isolation by organization (Anthropic: per workspace on the first-party API). Not shared across orgs. | n | n | n | n | n | KV | 1 | S |
| 21 | vLLM / SGLang / TensorRT-LLM / LMCache cache_salt | OSS docs/PRs | https://nvidia.github.io/TensorRT-LLM/latest/features/kvcache.html ; https://github.com/LMCache/LMCache/pull/3042 ; https://github.com/vllm-project/vllm/pull/39837 | Only requests with an identical salt share blocks (isolation, not dominance). LMCache adds per-salt quotas and S3 bucket isolation. Salt should be bound to authenticated tenant. | n | n (equality only) | n | n | n | KV | 1 | S |
| 22 | Gu et al., Auditing Prompt Caching in LM APIs | paper, ICML 2025 / arXiv 2502.07776 | https://proceedings.mlr.press/v267/gu25b.html | Timing audits detect cross-user prompt-cache sharing at 7 API providers. Motivates isolation. | n | n | n | n | n | KV | 1 | S |
| 23 | Mem0, Letta | OSS | https://mem0.ai/library/agent-memory/open-source-ai-agents-with-built-in-memory | Identity scoping (user/agent/tenant ids) and metadata filters. Letta shared blocks are not a permission model. Neither labels derived summaries. | n | n | n | n | n | TXT | 0-1 | S |
| 24 | APPA (Agentic Permissions Policy Algebra) | paper, arXiv 2607.24625, Jul 2026 | https://arxiv.org/abs/2607.24625 | Recoverable IFC for agents, with sanitizers and bounded casts. Not about caches. | p | n | n | p (sanitize/cast) | n | IFC | 1 | S |
| 25 | Permission-aware RAG (IEEE Access 2025; Google tdcommons; Policy-aware Vector Search arXiv 2606.19803) | papers | https://doi.org/10.1109/access.2025.3628960 ; https://www.tdcommons.org/dpubs_series/6948/ ; https://arxiv.org/abs/2606.19803 | Embedding-level ACLs; ACL pre-filtering of vector search. Retrieval-time only. | p (embeddings) | n | n | n | n | TXT | 1 | S/O mix |
| 26 | Readyset cache authorization | DB docs | https://readyset.io/docs/reference/cache-authorization | Re-checks user access per cache hit. A classical analogue, not LLM. | n | p | n | n | n | TXT | 1 | S |
| 27 | Yandex "KV cache as an agent runtime" | blog, 5 Sep 2026 | https://research.yandex.com/blog/the-kv-cache-as-an-agent-runtime | Shared physical KV blocks with different causal views per consumer (RoPE rotation). No security labels. Relevant only as a mechanism for position-independent reuse. | n | n | n | n | n | KV | 0 | O |

## Not examined (honest gaps)

- GPTCache, LangChain/LlamaIndex ACL filters, Mooncake and SGLang internals: not opened directly. Mooncake and SGLang were covered only via #4 and #10.
- vLLM RFC #16016 and CVE-2025-46570 were taken from citations in #4 and #10, not opened.
- Cloudflare: not searched.
- SpliceLeak (2606.21842), NDSS PromptPeek and InputSnatch: seen only as citations. They are side-channel attacks, which matter for the "compute-on-write kills timing channels" argument but not for the design.
- Closed-source vendor internals (Copilot, Glean, Rovo, Agentspace) may cache derived data with labels. Public docs say nothing either way.
- I never found a paper with a name like "label-lattice" or "memoization" combined with ACLs. Absence from a search index is weak evidence.

## Novelty verdict

**Whole idea: not found implemented or published as of 2026-10-25.** No source combines all six aspects. The nearest pieces:
- **Text/memory-level labels + dominance** (#1 AkasicMEM, #2 hectar tessera): intersection labels on derived text artifacts, reused by qualifying principals. Both are lazy or per-hit rather than eager, neither is KV-level, and neither keys artifacts by (content-version, label) for memoization.
- **KV-level sharing under permission** (#3, #4, #7-#11): binary, salt-equality, per-owner or detection-based. No lattice dominance or intersection labels over KV segments. UCSC Tessera only sketches ACL-scoped namespaces and revocation as future work.
- **Epoch + dependency manifest for revocation** (#13): folk practice in blogs, text-level answer caches only.

**Appears genuinely open (per this search):**
1. KV-level segments labelled by the intersection of source ACLs and shared by lattice dominance (not salt equality or exact entitlement-set equality), together with a signature-count / sharing-ratio analysis.
2. Eager compute-on-write per (content-version, label) as a deliberate design choice, with the timing channel argued away by construction. AkasicMEM explicitly argues for lazy re-evaluation instead, so this is a real design divergence and must be defended on cost grounds.
3. Declassification by re-derivation (recompute from the visible subset) as a first-class mechanism. AkasicMEM uses an NLI/reviewer exclusion, and FIDES uses declassification hatches. Neither re-derives.
4. ACL-epoch leases and tombstones applied uniformly across KV, summary, embedding and claim artifacts. UCSC Tessera's epochs are storage epochs only.
5. A unified labelled artifact store spanning KV, summaries, claims and embeddings. Existing work covers one tier each.

**Merely classical (do not claim as novel):**
- The lattice/dominance model and no-read-up (Denning 1976, Bell–LaPadula).
- Intersection-of-readers join (FIDES, Microsoft IFC docs, Glean's allowed_group_intersections).
- Version-keyed memoization.
- Per-hit authorization re-checks (Readyset).
- Monotonic epoch / lease revocation (distributed-systems folklore, now appearing in RAG-cache blogs).
- Provenance-graph cascade invalidation (PACMI, Zep/Graphiti).
- Salt-based KV isolation (vLLM, TRT-LLM, LMCache).

**Risks to the novelty claim:**
- AkasicMEM (Sep 2026) and the hectar-glitches Tessera overlap A/B/E at text level, and the UCSC Tessera/provenance-contract line is moving toward KV-level scoping. A paper should frame the contribution as "KV-level + eager + re-derivation + epochs, with measured signature explosion", and cite these as nearest work.
- Uncertainties: arXiv 2603.10726 naming (CacheSolidarity vs PrefixWall); #6, #14, and the vendor rows rely on search summaries; vendor internals are unknown.
