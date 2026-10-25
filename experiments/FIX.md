# FIX: Lazy-Meet Factoring (LMF) for the label lattice

Status: simulated and unit-tested against a reference model. Not measured on real ACLs, real models, or real join quality.

## 1. The problem in one paragraph

In the label lattice, a derived artifact (a KV segment, a summary, a claim list) is labelled with the intersection of the ACL audiences of the documents it was built from. The intersection is much narrower than any single input. The median artifact audience is about 0.6 of its narrowest input. So even when documents are widely shared, artifacts fragment into small audiences, and the shared cache degrades toward a per-user cache. In the Stage A sweep this passes narrowly at 5% private docs (40.8% of artifact read mass needs a label of 3 or fewer principals) and fails from about 30% private docs (59.3%), with 15% ad hoc shares (54.0%), and in the worst case (65.5%). The falsifier says to drop the idea if 50% or more of read mass needs labels of 3 or fewer principals. Documents alone pass at 8.5%.

## 2. The idea in plain words

The intersection is a rule about who may read something. We were also using it as a rule about how the work is organised, by baking it into the expensive computation. That is the mistake.

Do the expensive work once per document, labelled with that one document's audience. Keep the intersection as a cheap gate that is checked when someone reads. Combine the per-document pieces with a cheap join step only for a reader who is entitled to every piece, and cache that join output under the intersection label.

Documents are widely shared (8.5% of read mass is narrow), so per-document pieces share well. Only the cheap join is stuck with narrow labels. The meet is computed lazily at read time, never baked into the expensive work. Hence the name: Lazy-Meet Factoring.

## 3. How it works

1. **Components.** For each (document, version), compute the expensive per-chunk pieces once: the KV segment, the chunk note, the claim list. A component is a pure function of that one document's text plus a public prompt. Its provenance is exactly {doc}. Its label is that document's ACL. It is cached once and shared by every artifact that uses the document.
2. **Join.** An artifact over k documents is a cheap composition of k components: summary of notes, KV patch, claim merge. Output size and cost are modelled as RHO * k chunk units (RHO = 0.15 in the headline runs).
3. **Gate before lookup.** On a read, the system first asks the ACL service whether the principal is entitled to every input document. Only then does it look at any shared cache. A refused principal gets the same refusal whether the entry is hot or cold, and touches no cache or compute.
4. **Composite cache (tier 2).** The join output is cached under the intersection label. Entitled readers hit it. Composite provenance is the union of component provenances and is re-checked at read time as defence in depth. An option is to admit a composite only on its second read, which cuts entries by about 17%.
5. **Entitlement leases.** A principal's entitlement to a label is held as a lease. Push invalidation drops the lease and recomputes nothing (components and composites stay valid for everyone else). If the push is lost, staleness is bounded by the lease length.
6. **Edits and deletes.** A content edit or delete tombstones the component and every composite that contains it. An ACL change alone does not recompute anything.

### Hybrid variant H (narrow only)

Apply LMF only to artifacts whose intersection audience is at most T principals (T = 3 or 10). Wider artifacts stay monolithic under their intersection label, with no join step and no composition quality risk. This costs more compute than pure LMF, because monolithic wide artifacts lose cross-artifact reuse. The result on the falsifier metric is nearly the same.

## 4. What I compared and why LMF won

| Direction | What I did | Result |
|---|---|---|
| (a) Decomposed artifacts | Arm A: this fix (LMF) | Passes at 30% private and in the worst case. Chosen. |
| (b) Label coarsening by group closure | Arm B: round the intersection down to org groups fully inside it, plus leftover users | Worse than baseline (75.7% at medium/30% versus 59.3%). Dominated, see below. |
| (c) Tiered public core plus delta | Folded into LMF. A "public core" is just the components of widely shared docs, the delta is the join over the narrow ones | No separate gain beyond LMF |
| (d) Lazy/eager hybrid | Hybrid H: LMF only on narrow artifacts | Same pass/fail, about 1.5x the compute of pure LMF, but only 55% to 66% of artifact reads touch composition |
| (e) k-anonymity audience merging | Not implemented | Rejected on principle. Merging audiences means serving some principals content from documents they cannot read, which breaks the guarantee. Any sound version is a round-down, which is arm B |
| (f) Cost model | M2 metric and rho sweep | See section 6 |
| Own: class-partial factoring | Arm C: one partial per (artifact, doc-ACL class) | Same label benefit as LMF, but 268,784 entries versus 141,179 and no cross-artifact reuse. Dominated |

Why arm B fails: a cover made of groups fully contained in the intersection is a subset of the intersection. Round-down coarsening can reduce label cardinality but never enlarges an audience. Label cardinality is not what is failing. The audience size is. Any sound label for a monolithic artifact is at most the intersection, so no relabelling can fix a monolithic artifact. The only way out is to stop having monolithic expensive artifacts, which is what LMF does. Cover violations were 0, so arm B is sound but useless.

## 5. Results (5 seeds, 10,000 users, mean [min to max])

"Before" is the artifact read mass needing a label of 3 or fewer principals (the original falsifier metric). "After" has two numbers:
- **M1**: component read mass whose document audience is 3 or fewer. This is the cleanest analogue of the original metric.
- **M2**: cost-weighted unshareable fraction. It counts component work on narrow documents plus the join work (weighted by rho) when the artifact audience is 3 or fewer, divided by total work. This is the stricter number and includes the join penalty. Pass or fail is judged on M2.

### Before and after, key scenarios (medium structure unless named)

| Scenario | Before (artifact, falsifier) | After M1 | After M2 (rho 0.15) | Verdict after | Arm B |
|---|---|---|---|---|---|
| medium, 5% private | 40.8% [33.6-49.6] pass | 4.5% | 10.3% [8.5-12.7] | PASS 5/5 | 68.0% FAIL |
| medium, 20% private | 50.2% [45.3-54.0] mixed (2/5) | 14.7% | 19.9% | PASS 5/5 | 78.6% FAIL |
| **medium, 30% private** | **59.3% [51.8-63.5] FAIL** | 21.9% | **27.5% [25.5-30.9]** | **PASS 5/5** | 75.7% FAIL |
| few_large, 30% private | 56.6% FAIL | 19.7% | 24.8% | PASS 5/5 | 84.3% FAIL |
| many_small, 30% private | 60.1% FAIL | 23.3% | 28.9% | PASS 5/5 | 76.8% FAIL |
| medium, 40% private | 66.9% FAIL | 32.8% | 37.7% | PASS 5/5 | 82.4% FAIL |
| medium, 50% private | 78.7% FAIL | 45.7% | 50.3% [41.8-57.4] | MIXED (3/5) | 88.4% FAIL |
| medium, 60% private | 81.3% FAIL | 50.9% | 55.1% | MIXED (1/5) | 88.0% FAIL |
| many_small, 60% private | 86.5% FAIL | 59.1% | 63.0% | FAIL | 91.9% FAIL |
| ad hoc shares 15% | 54.0% FAIL | 8.6% | 15.6% | PASS 5/5 | 75.8% FAIL |
| mixed: 15% private + 10% ad hoc | 54.2% FAIL | 14.8% | 20.9% | PASS 5/5 | 75.3% FAIL |
| **worst-case combo** | **65.5% [58.1-68.1] FAIL** | 24.9% | **31.3% [28.6-34.6]** | **PASS 5/5** | 78.0% FAIL |
| best-case combo | 9.7% pass | 0.0% | 1.7% | PASS 5/5 | 53.1% mixed |
| priv 20%, 4x private population | 75.5% FAIL | 39.1% | 43.8% [34.7-49.6] | PASS 5/5, thin margin | 86.9% FAIL |

Full tables for all 3 group structures and all private fractions 0 to 60% are in `fix_tables.md`. Raw per-run data is in `runs_fix/` and `results_fix.json`.

### Hit rate, storage, compute (rho 0.15)

| Scenario | Per-user artifact hit rate | Old shared lattice hit rate | LMF component hit rate | Entries per-user | Entries LMF | Entries LMF (admit on 2nd read) | Storage units LMF / per-user | Compute LMF / per-user | Compute LMF / old shared |
|---|---|---|---|---|---|---|---|---|---|
| medium 5% | 74.4% | 91.9% | 98.0% | 255,693 | 141,983 | 117,513 | 0.14 | 0.14 | 0.39 |
| medium 30% | 80.6% | 91.9% | 97.8% | 193,702 | 141,179 | 116,709 | 0.19 | 0.19 | 0.42 |
| few_large 30% | 77.4% | 91.9% | 97.9% | 226,085 | 141,419 | 116,948 | 0.15 | 0.15 | 0.41 |
| many_small 30% | 82.6% | 91.9% | 97.8% | 173,767 | 141,047 | 116,577 | 0.22 | 0.22 | 0.43 |
| worst case | 83.1% | 91.9% | 97.6% | 168,660 | 141,240 | 116,769 | 0.23 | 0.23 | 0.43 |

Read the hit rate column with care. The old shared lattice's artifact hit rate is 91.9% in every scenario, including the ones that fail. That is because hit rate under perfect sharing depends only on how skewed the reads are, not on audience size. So hit rate does not separate pass from fail. The falsifier metric and the work-weighted M2 do. That is why the pass or fail judgement uses M2.

Entries versus units: LMF stores more entries than the old shared lattice (141,179 versus 80,777 at medium/30%) because it holds components and composites. It stores fewer chunk units, because components are shared across artifacts. Metadata overhead per entry is not modelled.

### Join cost sweep (M2, mean)

| Scenario | rho 0.05 | rho 0.15 | rho 0.30 | rho 1.0 | Break-even rho (M2 = 50%) |
|---|---|---|---|---|---|
| medium 5% | 6.6% | 10.3% | 14.7% | 26.5% | 15.5 or more |
| medium 30% | 23.9% | 27.5% | 31.8% | 43.3% | 1.50 to 2.47 |
| many_small 30% | 25.3% | 28.9% | 33.2% | 44.8% | 1.11 to 5.04 |
| worst case | 27.2% | 31.3% | 36.1% | 49.3% | 0.89 to 1.41 |
| ad hoc 15% | 11.2% | 15.6% | 21.0% | 35.4% | 2.76 to 4.25 |

In plain words: the fix keeps passing as long as the join costs less than roughly the same as processing one chunk per input. In the worst case the margin is thin: at rho 1.0 it is 49.3%.

### Hybrid H (rho 0.15)

| Scenario | Before | Pure LMF M2 | H(T=3) M2 | Share of artifact reads on LMF path | H(T=3) compute / per-user | H(T=3) compute / old shared |
|---|---|---|---|---|---|---|
| medium 5% | 40.8% | 10.3% | 11.0% | 41% | 0.27 | 0.77 |
| medium 30% | 59.3% | 27.5% | 28.8% | 59% | 0.30 | 0.66 |
| worst case | 65.5% | 31.3% | 32.4% | 66% | 0.33 | 0.62 |
| ad hoc 15% | 54.0% | 15.6% | 16.4% | 54% | 0.29 | 0.68 |

H(T=10) is about the same on M2 and slightly cheaper. So H passes everywhere pure LMF passes. The honest point is that the share of artifact reads on the composition path is about the same as the old failing mass (55% to 66% when the baseline fails), so the quality risk of composition is not confined to a small slice.

### Compute and storage versus the alternatives (medium 30%)

| Design | Entries | Compute vs per-user cache | Compute vs old shared lattice |
|---|---|---|---|
| Old intersection lattice | 80,777 | 0.45 | 1.00 |
| LMF (rho 0.15) | 141,179 | 0.19 | 0.42 |
| Arm B group cover | 121,102 | 0.70 | 1.55 |
| Arm C class-partial | 268,784 | 0.50 | 1.13 |

LMF is cheaper than the old lattice in compute because documents are reused across artifacts. That gain is real in the model, but it depends on how often the same document appears in many artifacts, which comes from the synthetic Zipf document popularity. At rho 1.0, LMF costs about 1.27 times the old shared lattice, so it would lose on raw compute there (it still wins on sharing).

## 6. What it costs

- **Join work.** Every composite pays RHO * k units once per intersection label. At rho 0.15 this gives M2 of 27.5% at medium/30% and 31.3% in the worst case. Break-even is 1.5 to 2.5 for medium/30% and 0.9 to 1.4 in the worst case.
- **Compute.** About 0.14 to 0.23 of a per-user cache, and about 0.4 to 0.45 of the old shared lattice, at rho 0.15.
- **Storage.** About 0.14 to 0.23 of per-user storage in chunk units. Entry count is 1.75x the old shared lattice at medium/30%. Admitting composites on the second read trims that to 116,709 entries.
- **Read path latency.** One extra step on a composite miss (the join). An ACL check on every read, before any cache lookup. Leases amortise that check.
- **Quality.** Not measured. See section 8.
- **Complexity.** Two cache tiers, provenance tracking, leases, and tombstone propagation.

## 7. Security argument

Guarantee: no principal is ever served content derived from a document they cannot read.

Why it holds in the design:
1. Components depend on one document's text plus a public prompt. No other document can leak into a component. Provenance is exactly {doc}.
2. A composite is built only for a principal entitled to every input, and its provenance is the union of its components. It is stored under the intersection label.
3. The gate runs before any shared-cache lookup. A refused principal never learns whether an entry exists, and no timing or hit or miss difference exists for them.
4. Provenance is re-checked at read time against current ACLs, so a stale label cannot grant access on its own.

Tested in `test_lmf.py` (15 tests, all pass):
- Component purity.
- A composite is only ever built for the intersection with no unreadable source.
- A cached composite does not help an unentitled principal.
- Refusal is identical hot or cold and touches no shared cache or compute.
- A randomized property test with push invalidation: no principal ever receives a marker for a document they cannot read.
- A randomized test with lost push: staleness is bounded by the lease.
- Arm B cover groups always lie inside the true intersection.
- Simulated readers are entitled to every component of their artifacts.

Revocation behaviour in tests:
- With push, a revoked principal is refused immediately and nobody else recomputes anything.
- With lost push, the principal is refused within the lease length. This is the bounded staleness window and is the real tradeoff: a long lease means a longer window.
- A delayed push is applied on delivery.
- An unrelated revocation disturbs nothing.
- An edit tombstones only dependants. A delete is handled. An ACL widen then tighten works.

I checked that the tests have teeth. Disabling push gave 3 failures. Skipping the gate gave 1 failure.

The existing `test_revocation.py` (9 tests) still passes.

### Leaks that remain (be honest)

- **Co-reader timing signal.** An entitled reader who gets a fast hit can infer that someone else entitled to the same label already read it. That is a signal about the activity of other entitled principals. It does not reveal content they cannot read. Mitigation: constant-time response or randomised delay, at a cost.
- **Existence and size oracles for entitled readers.** A component or composite size can reveal something about the document. This is fine only because the reader is entitled to every input. The danger is a future partial-result mode (serve a composite over only the readable subset). If that mode says "2 of 5 sources hidden", it leaks existence. I did not build it. If it is built, do not expose counts.
- **Eviction pressure.** A shared pool means one principal's load can evict another's entries. That only affects timing of data the victim can already read.
- **Component purity is an assumption about the model stack.** For KV segments it needs position-independent or context-free computation. Any hidden dependence on neighbouring documents breaks the guarantee. The tests assert purity only in the reference model.
- **ACL service is trusted.** Correctness depends on it being fresh up to the lease.
- **Memorisation.** If a composition model is later fine-tuned on outputs, that is out of scope.

## 8. What remains unproven

1. **Join quality.** I model the join as cost RHO * k and assume it equals a monolithic computation in quality. That is exactly decomposable for claim lists (a union), approximately so for KV patching (the EPIC style composable reuse in PRIOR_ART.md suggests it can work, with recompute of some tokens), and lossy for summaries (a summary of notes loses cross-document links). Stage B must measure quality per artifact type. For summaries the fallback is the old intersection lattice or hybrid H.
2. **Real rho.** Unmeasured. The worst-case margin only holds while rho stays below about 0.9 to 1.4.
3. **Cross-artifact document reuse.** The compute advantage over the old lattice depends on the synthetic popularity model. Real artifact-to-document overlap may be weaker.
4. **The doc-level floor.** LMF cannot beat the document read mass. At 50% to 60% private docs, M2 is 50.3% to 55.1% (mixed) and 63.0% fails at many_small/60%. If real data has that much narrow content, nothing in this family helps, because the documents themselves are unshareable.
5. **Thin margin cases.** priv20 with 4x private population passes at 43.8% but one seed reached 49.6%. The doc-level metric itself fails there.
6. **Synthetic ACLs.** Group structures, share rates, and popularity are all invented. The sweep covers 3 structures, 5 seeds, and several sensitivities, but they are still assumptions.
7. **Lease length.** The simulation shows bounded staleness, but the right lease for a given organisation is a policy choice that I have not tuned.
8. **Entry metadata overhead and eviction.** Not modelled. Capacity pressure may change the hit rates.
9. **Operational behaviour at scale.** Lost-push frequency, tombstone storms on popular documents, and ACL service load are untested.

## 9. What real ACL exports are needed

To replace the synthetic inputs with real ones:
1. **Document ACL snapshot.** Per document: id, version, owner, and the effective audience (users after group expansion), plus the raw ACL (groups, users, link-sharing flags) so that group closure can be checked.
2. **Group membership.** The full membership graph, including nested groups, with sizes and churn history.
3. **Read logs.** Per read: principal, document or artifact id, timestamp. This gives the real popularity skew and the real read mass by audience size.
4. **Artifact lineage.** For existing derived artifacts (summaries, retrieval chunks, caches): the set of source documents. This gives the real k and the real document overlap between artifacts.
5. **ACL change history.** Share, unshare, group changes with timestamps. This gives real revocation rate for sizing leases and tombstone load.
6. **Edit history.** For tombstone rates.
7. **Measured join cost and quality.** From a prototype: compute time of the monolithic versus the factored computation per artifact type (rho), plus a quality comparison.

The first three are enough to re-run the document-level floor (is the doc read mass below 50% narrow?) and M1. Items 4 and 7 are needed for M2 and to settle whether the join is good enough.

## 10. Files

All in `this folder`. Existing files are untouched.

- `fix.py`: arms A (LMF), B, C, and hybrid H, replaying the same RNG pipeline as `sim.py` so the baseline reproduces bit for bit.
- `run_fix.py`: the sweep (165 runs, 5 seeds). Outputs `results_fix.json` and `runs_fix/`.
- `make_fix_report.py`: generates `fix_tables.md` (full tables).
- `lmf_store.py`: reference model of the LMF store with leases, push, tombstones, and counters.
- `test_lmf.py`: 15 security and revocation tests.
- `FIX.md`: this file.

Run: `python3 run_fix.py && python3 make_fix_report.py && python3 test_lmf.py && python3 test_revocation.py`
