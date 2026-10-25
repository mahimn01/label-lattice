import json
R = json.load(open("results_fix.json")); S = R["scenarios"]; K = len(R["seeds"])
def pc(m, d=1): return f"{100*m['mean']:.{d}f}% [{100*m['min']:.{d}f}-{100*m['max']:.{d}f}]"
def x(m, d=2): return f"{m['mean']:.{d}f}"
def vd(n): return "PASS" if n == K else ("FAIL" if n == 0 else f"MIXED ({n}/{K})")
out = []
def table(h, rows):
    out.append("| " + " | ".join(h) + " |"); out.append("|" + "|".join("---" for _ in h) + "|")
    for r in rows: out.append("| " + " | ".join(str(c) for c in r) + " |")
    out.append("")
def row(name, sc):
    M = sc["metrics"]; g = lambda k: M[k]
    lm = sum(1 for _ in [0])
    return name, sc
def m2pass(sc, rho="0.15"):
    return None
def per_seed_pass(name, key):
    import glob
    n = 0
    for s in R["seeds"]:
        r = json.load(open(f"runs_fix/{name.replace('/', '__')}__s{s}.json"))
        n += key(r)
    return n
names = list(S)
def main_rows(sel):
    rows = []
    for n in sel:
        sc = S[n]; M = sc["metrics"]
        nb = per_seed_pass(n, lambda r: r["base"]["mass_le3"] < 0.5)
        nl = per_seed_pass(n, lambda r: r["A"]["by_rho"]["0.15"]["M2_cost_weighted_unshareable"] < 0.5)
        nb_ = per_seed_pass(n, lambda r: r["B"]["mass_le3"] < 0.5)
        rows.append((n.replace("grid/", ""), pc(M["base.mass_le3"]), vd(nb), pc(M["A.M1_comp_mass_le3"]),
                     pc(M["A.rho0.15.M2_cost_weighted_unshareable"]), vd(nl), pc(M["B.mass_le3"]), vd(nb_)))
    return rows
H1 = ["scenario", "BEFORE artifact mass <=3 principals", "before", "LMF component mass <=3", "LMF cost-weighted unshareable (rho .15)", "LMF verdict", "arm B cover mass <=3", "arm B"]
out.append("### Before / after: falsifier metric (5 seeds, mean [min-max])\n")
for st in ("few_large", "medium", "many_small"):
    out.append(f"**{st}**\n")
    table(H1, main_rows([f"grid/{st}/priv{p:02d}" for p in (0, 5, 10, 20, 30, 40, 50, 60)]))
out.append("**Sensitivity and combos (medium unless named)**\n")
table(H1, main_rows([n for n in names if not n.startswith("grid/")]))
H2 = ["scenario", "per-user artifact hit rate", "old shared artifact hit rate", "LMF component hit rate (shared)", "entries per-user", "entries LMF (comp+composite)", "entries LMF (admit composite on 2nd read)", "storage units LMF / per-user", "compute LMF / per-user", "compute LMF / old shared lattice", "break-even rho"]
def cost_rows(sel):
    rows = []
    for n in sel:
        M = S[n]["metrics"]
        be = M["A.breakeven_rho"]
        bes = "never (join alone <50%)" if be["max"] == float("inf") and be["min"] == float("inf") else (f"{be['min']:.2f}-{be['max']:.2f}" if be["max"] != float("inf") else f">={be['min']:.2f}")
        rows.append((n.replace("grid/", ""), pc(M["base.hit_rate_per_user"]), pc(M["base.hit_rate_shared"]), pc(M["A.comp_hit_rate_shared"]),
                     f"{M['base.entries_per_user']['mean']:,.0f}", f"{M['A.entries_total']['mean']:,.0f}", f"{M['A.entries_total_admit2']['mean']:,.0f}",
                     x(M["A.rho0.15.storage_vs_per_user"]), x(M["A.rho0.15.units_vs_per_user"]), x(M["A.rho0.15.units_vs_old_shared"]), bes))
    return rows
out.append("### Hit rate, storage and compute (rho = 0.15)\n")
sel = [f"grid/medium/priv{p:02d}" for p in (5, 20, 30, 50)] + ["grid/few_large/priv30", "grid/many_small/priv30", "sens/adhoc_frac=0.15", "combo/worst_case", "combo/best_case", "sens/priv20_pop_mult=4.0"]
table(H2, cost_rows(sel))
out.append("### Join cost sweep (cost-weighted unshareable fraction; rho = join cost / chunk work)\n")
rows = []
for n in ["grid/medium/priv05", "grid/medium/priv30", "grid/many_small/priv30", "combo/worst_case", "sens/adhoc_frac=0.15"]:
    M = S[n]["metrics"]
    rows.append((n.replace("grid/", ""),) + tuple(pc(M[f"A.rho{r}.M2_cost_weighted_unshareable"]) for r in ("0.05", "0.15", "0.3", "1.0")) +
                tuple(x(M[f"A.rho{r}.units_vs_per_user"]) for r in ("0.05", "0.15", "0.3", "1.0")) + tuple(x(M[f"A.rho{r}.units_vs_old_shared"]) for r in ("0.05", "0.15", "0.3", "1.0")))
table(["scenario", "M2 rho .05", "M2 .15", "M2 .30", "M2 1.0", "compute/per-user .05", ".15", ".30", "1.0", "compute/old shared .05", ".15", ".30", "1.0"], rows)
out.append("### Arm comparison at medium / 30% private (mean over seeds)\n")
M = S["grid/medium/priv30"]["metrics"]
table(["arm", "effective-label mass <=3", "entries", "compute vs per-user", "compute vs old shared", "note"], [
 ("base (intersection label)", pc(M["base.mass_le3"]), f"{M['base.entries_shared']['mean']:,.0f}", x(M["base.units_shared"]) if False else f"{M['base.units_shared']['mean']/M['base.units_per_user']['mean']:.2f}", "1.00", "fails"),
 ("A LMF (rho .15)", pc(M["A.rho0.15.M2_cost_weighted_unshareable"]), f"{M['A.entries_total']['mean']:,.0f}", x(M["A.rho0.15.units_vs_per_user"]), x(M["A.rho0.15.units_vs_old_shared"]), "passes; join is the only narrow-label work"),
 ("B group-closure cover", pc(M["B.mass_le3"]), f"{M['B.entries']['mean']:,.0f}", x(M["B.units_vs_per_user"]), x(M["B.units_vs_old_shared"]), "cover is a subset of the intersection, so it can only shrink audiences"),
 ("C class-partial", pc(M["A.M1_comp_mass_le3"]) + " (same labels as A)", f"{M['C.entries']['mean']:,.0f}", f"{M['C.units_rho0.15']['mean']/M['base.units_per_user']['mean']:.2f}", f"{M['C.units_rho0.15']['mean']/M['base.units_shared']['mean']:.2f}", "same label benefit, but no cross-artifact reuse"),
])
out.append("### Hybrid H: LMF only for narrow artifacts, wide ones stay monolithic (rho = 0.15)\n")
rows = []
for n in ["grid/medium/priv05", "grid/medium/priv30", "grid/many_small/priv30", "grid/few_large/priv30", "combo/worst_case", "sens/adhoc_frac=0.15"]:
    M = S[n]["metrics"]
    rows.append((n.replace("grid/", ""), pc(M["base.mass_le3"]), pc(M["A.rho0.15.M2_cost_weighted_unshareable"]),
        pc(M["H.T3.rho0.15.M2"]), pc(M["H.T3.lmf_read_share"], 0), x(M["H.T3.rho0.15.units_vs_per_user"]), x(M["H.T3.rho0.15.units_vs_old_shared"]),
        pc(M["H.T10.rho0.15.M2"]), pc(M["H.T10.lmf_read_share"], 0), x(M["H.T10.rho0.15.units_vs_per_user"]), x(M["H.T10.rho0.15.units_vs_old_shared"])))
table(["scenario", "before", "pure LMF M2", "H(T=3) M2", "H(T=3) share of artifact reads on LMF path", "H(T=3) compute / per-user", "H(T=3) compute / old shared", "H(T=10) M2", "H(T=10) share on LMF path", "H(T=10) compute / per-user", "H(T=10) compute / old shared"], rows)
open("fix_tables.md", "w").write("\n".join(out))
print("\n".join(out))
