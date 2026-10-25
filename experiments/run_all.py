"""Run all Stage-A scenarios x seeds; caches each run in runs/; aggregates into results.json."""
import json, os, sys, time
from multiprocessing import Pool
from dataclasses import asdict
import numpy as np
from sim import Params, run

SEEDS = [1, 2, 3, 4, 5]
PGRID = [0, 5, 10, 20, 30, 40, 50, 60, 70, 80]
STRUCTS = ["few_large", "medium", "many_small"]

def scenarios():
    S = []
    def add(name, group, **kw):
        S.append(Params(name=name, **kw)); S[-1].__dict__["group"] = group
    for st in STRUCTS:
        for p in PGRID:
            add(f"grid/{st}/priv{p:02d}", "grid", structure=st, private_frac=p / 100)
    base = dict(structure="medium", private_frac=0.05)
    for v in (0.0, 0.5, 0.75):
        add(f"sens/small_frac={v}", "sens", **{**base, "small_frac": v})
    for v in (0.0, 0.15):
        add(f"sens/adhoc_frac={v}", "sens", **{**base, "adhoc_frac": v})
    for p in (0.2, 0.5):
        for v in (0.25, 4.0):
            add(f"sens/priv{int(p*100)}_pop_mult={v}", "sens", structure="medium", private_frac=p, private_pop_mult=v)
    add("sens/art_mode=random", "sens", **{**base, "art_mode": "random"})
    for v in (0.7, 1.3):
        add(f"sens/doc_zipf={v}", "sens", **{**base, "doc_zipf": v})
    for v in (0.2, 0.95):
        add(f"sens/local_proj_prob={v}", "sens", **{**base, "local_proj_prob": v})
    add("combo/worst_case", "combo", structure="many_small", private_frac=0.2, small_frac=0.5, adhoc_frac=0.10)
    add("combo/best_case", "combo", structure="few_large", private_frac=0.0, small_frac=0.10, adhoc_frac=0.0)
    return S

def job(args):
    P, seed = args
    fn = f"runs/{P.name.replace('/', '__')}__s{seed}.json"
    if os.path.exists(fn):
        return fn
    r = run(P, seed)
    r["scenario"] = P.name
    json.dump(r, open(fn + ".tmp", "w"))
    os.replace(fn + ".tmp", fn)
    return fn

def agg(vals):
    a = np.array(vals, float)
    return dict(mean=float(a.mean()), min=float(a.min()), max=float(a.max()))

def flat(r):
    d = {}
    s, dl, al, dr, ar = r["signatures"], r["doc_labels"], r["artifact_labels"], r["doc_reads"], r["artifact_reads"]
    d["sig_group"] = s["distinct_group_signatures"]; d["sig_relevant"] = s["distinct_signatures_acl_relevant_groups_only"]
    d["sig_with_grants"] = s["distinct_signatures_incl_individual_grants"]; d["frac_users_singleton_sig"] = s["frac_users_in_singleton_signature"]
    d["doc_labels_acl"] = dl["distinct_acl_sets"]; d["doc_labels_aud"] = dl["distinct_audiences"]
    d["doc_label_frac_le3"] = dl["audience_dist"]["frac_labels_le3"]; d["doc_label_median_aud"] = dl["audience_dist"]["pct"]["50"]
    d["art_labels_sym"] = al["distinct_symbolic_input_sets"]; d["art_labels_aud"] = al["distinct_audiences"]
    d["art_label_frac_le3"] = al["audience_dist"]["frac_labels_le3"]; d["art_label_median_aud"] = al["audience_dist"]["pct"]["50"]
    d["art_frac_empty"] = al["frac_empty"]; d["art_median_shrink"] = al["median_shrink_ratio"]; d["art_mean_shrink"] = al["mean_shrink_ratio"]
    for pre, m in (("doc", dr), ("art", ar)):
        for k in ("potential_shareable_mass", "realized_shared_mass", "mass_aud_le1", "mass_aud_le3", "mass_aud_le10", "mass_aud_le100",
                  "hit_rate_per_user_cache", "hit_rate_shared_lazy", "storage_ratio_per_user_over_shared", "median_audience_read_weighted"):
            d[f"{pre}_{k}"] = m[k]
    d["doc_read_mass_private"] = dr["read_mass_by_doc_type"]["private"]
    d["docs_pass"] = float(r["falsifier"]["docs_pass"]); d["art_pass"] = float(r["falsifier"]["artifacts_pass"])
    return d

def main():
    os.makedirs("runs", exist_ok=True)
    S = scenarios()
    jobs = [(P, s) for P in S for s in SEEDS]
    t0 = time.time()
    with Pool(int(os.environ.get("NPROC", 3))) as pool:
        for i, fn in enumerate(pool.imap_unordered(job, jobs)):
            if i % 10 == 0:
                print(i, len(jobs), round(time.time() - t0), flush=True)
    out = dict(seeds=SEEDS, scenarios={}, raw_note="per-run raw files in runs/")
    for P in S:
        runs = [json.load(open(f"runs/{P.name.replace('/', '__')}__s{s}.json")) for s in SEEDS]
        rows = [flat(r) for r in runs]
        out["scenarios"][P.name] = dict(
            group=P.__dict__.get("group"), params=asdict(P),
            metrics={k: agg([r[k] for r in rows]) for k in rows[0]},
            per_seed=rows,
            # audience-size distributions (seed-mean)
            hist_labels=runs[0]["hist_labels"],
            doc_label_count_by_bin=np.mean([r["doc_labels"]["audience_dist"]["count_by_bin"] for r in runs], axis=0).tolist(),
            art_label_count_by_bin=np.mean([r["artifact_labels"]["audience_dist"]["count_by_bin"] for r in runs], axis=0).tolist(),
            doc_read_mass_by_bin=np.mean([r["doc_reads"]["read_mass_by_audience_bin"] for r in runs], axis=0).tolist(),
            art_read_mass_by_bin=np.mean([r["artifact_reads"]["read_mass_by_audience_bin"] for r in runs], axis=0).tolist(),
            doc_audience_pct=runs[0]["doc_labels"]["audience_dist"]["pct"],
            verdict=dict(
                docs_pass_all_seeds=all(r["falsifier"]["docs_pass"] for r in runs),
                art_pass_all_seeds=all(r["falsifier"]["artifacts_pass"] for r in runs),
                docs_seeds_failing=sum(not r["falsifier"]["docs_pass"] for r in runs),
                art_seeds_failing=sum(not r["falsifier"]["artifacts_pass"] for r in runs)),
        )
    json.dump(out, open("results.json", "w"), indent=1)
    print("done", round(time.time() - t0))

if __name__ == "__main__":
    main()
