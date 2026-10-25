import json
R = json.load(open("results.json"))
S = R["scenarios"]
def pc(m, d=1): return f"{100*m['mean']:.{d}f}% [{100*m['min']:.{d}f}–{100*m['max']:.{d}f}]"
def nm(m, d=0): return f"{m['mean']:,.{d}f} [{m['min']:,.{d}f}–{m['max']:,.{d}f}]"
def vd(sc, which):
    n = sc["verdict"][f"{which}_seeds_failing"]; k = len(R["seeds"])
    return "PASS" if n == 0 else ("FAIL" if n == k else f"MIXED ({k-n}/{k} pass)")
out = []
def table(headers, rows):
    out.append("| " + " | ".join(headers) + " |"); out.append("|" + "|".join("---" for _ in headers) + "|")
    for r in rows: out.append("| " + " | ".join(str(x) for x in r) + " |")
    out.append("")
b = S["grid/medium/priv05"]; M = b["metrics"]
out.append("### Baseline scenario (medium structure, 5% private docs), mean [min–max] over 5 seeds\n")
table(["Measure", "Value"], [
 ("(a) distinct entitlement signatures (effective group set), of 10,000 users", nm(M["sig_group"])),
 ("(a) same, counting only groups that appear in some ACL", nm(M["sig_relevant"])),
 ("(a) same, plus users with an individual grant (private/ad-hoc doc) made unique", nm(M["sig_with_grants"])),
 ("(a) users alone in their signature class", pc(M["frac_users_singleton_sig"])),
 ("(b) distinct document labels - by ACL set (symbolic)", nm(M["doc_labels_acl"])),
 ("(b) distinct document labels - by audience (canonical)", nm(M["doc_labels_aud"])),
 ("(c) distinct derived-artifact labels - symbolic (set of input ACLs)", nm(M["art_labels_sym"])),
 ("(c) distinct derived-artifact labels - by audience (canonical)", nm(M["art_labels_aud"])),
 ("(d) median principals per doc label (over distinct labels)", nm(M["doc_label_median_aud"], 1)),
 ("(d) median principals per artifact label", nm(M["art_label_median_aud"], 1)),
 ("(d) share of distinct doc labels with ≤3 principals", pc(M["doc_label_frac_le3"])),
 ("(d) share of distinct artifact labels with ≤3 principals", pc(M["art_label_frac_le3"])),
 ("(e) doc read mass on items with audience ≥2 (potential sharing)", pc(M["doc_potential_shareable_mass"])),
 ("(e) doc read mass on items actually read by ≥2 distinct users in the log (realized)", pc(M["doc_realized_shared_mass"])),
 ("(e) lazy hit rate: per-user cache / shared label-keyed store (eager = 100%)", f"{pc(M['doc_hit_rate_per_user_cache'])} / {pc(M['doc_hit_rate_shared_lazy'])}"),
 ("(e) storage ratio per-user store ÷ shared store (docs)", nm(M["doc_storage_ratio_per_user_over_shared"], 2) + "×"),
 ("(f) doc read mass needing label audience ≤3 principals  [falsifier: ≥50% ⇒ drop]", f"**{pc(M['doc_mass_aud_le3'])}** → {vd(b,'docs')}"),
 ("(g) artifact read mass on labels with ≤3 principals", f"**{pc(M['art_mass_aud_le3'])}** → {vd(b,'art')}"),
 ("(g) artifact read mass realized shared (≥2 users) / storage ratio", f"{pc(M['art_realized_shared_mass'])} / {nm(M['art_storage_ratio_per_user_over_shared'],2)}×"),
 ("(g) artifacts: median audience ÷ smallest input audience", nm(M["art_median_shrink"], 2)),
])
hl = b["hist_labels"]
out.append("#### (d) Distribution of label audience sizes, baseline (seed mean)\n")
rows = []
for i, l in enumerate(hl):
    rows.append((l, f"{b['doc_label_count_by_bin'][i]:,.0f}", f"{100*b['doc_read_mass_by_bin'][i]:.1f}%",
                 f"{b['art_label_count_by_bin'][i]:,.0f}", f"{100*b['art_read_mass_by_bin'][i]:.1f}%"))
table(["Principals per label", "# distinct doc labels", "doc read mass", "# distinct artifact labels", "artifact read mass"], rows)

out.append("### Sweep: private-doc fraction × ACL structure (5 seeds; mean [min–max]; verdict vs 50% threshold)\n")
for st, desc in (("few_large", "few large groups"), ("medium", "medium (baseline)"), ("many_small", "many small groups")):
    out.append(f"**Structure: {st} - {desc}**\n")
    rows = []
    for p in (0, 5, 10, 20, 30, 40, 50, 60, 70, 80):
        sc = S[f"grid/{st}/priv{p:02d}"]; m = sc["metrics"]
        rows.append((f"{p}%", f"{m['sig_group']['mean']:,.0f}", f"{m['doc_labels_aud']['mean']:,.0f}", f"{m['art_labels_aud']['mean']:,.0f}",
                     pc(m["doc_realized_shared_mass"]), f"{m['doc_storage_ratio_per_user_over_shared']['mean']:.1f}×",
                     pc(m["doc_mass_aud_le3"]), vd(sc, "docs"), pc(m["art_mass_aud_le3"]), vd(sc, "art")))
    table(["private docs", "signatures", "doc labels (aud.)", "artifact labels (aud.)", "doc realized-shared mass", "storage ratio (docs)",
           "(f) doc mass ≤3", "(f) verdict", "(g) artifact mass ≤3", "(g) verdict"], rows)

out.append("### Sensitivity (medium structure unless noted; baseline = 5% private, 25% small-group, 3% ad-hoc, Zipf 1.0, creator-coherent artifacts)\n")
rows = []
order = [k for k in S if k.startswith("sens/") or k.startswith("combo/")]
for k in ["grid/medium/priv05"] + order + ["grid/medium/priv20", "grid/medium/priv50"]:
    sc = S[k]; m = sc["metrics"]; p = sc["params"]
    desc = f"struct={p['structure']}, priv={p['private_frac']:.0%}, small={p['small_frac']:.0%}, adhoc={p['adhoc_frac']:.0%}, popmult={p['private_pop_mult']}, zipf={p['doc_zipf']}, art={p['art_mode']}, localproj={p['local_proj_prob']}"
    rows.append((k, desc, pc(m["doc_mass_aud_le3"]), vd(sc, "docs"), pc(m["art_mass_aud_le3"]), vd(sc, "art"), pc(m["doc_realized_shared_mass"]), f"{m['doc_storage_ratio_per_user_over_shared']['mean']:.1f}×", f"{m['sig_group']['mean']:,.0f}"))
table(["scenario", "parameters", "(f) doc mass ≤3", "(f)", "(g) artifact mass ≤3", "(g)", "doc realized-shared", "doc storage ratio", "signatures"], rows)
open("tables.md", "w").write("\n".join(out))
print("\n".join(out))
