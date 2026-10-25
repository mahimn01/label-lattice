"""Sweep for the LMF fix: same scenarios/seeds as run_all.py (subset + extras). Caches in runs_fix/, aggregates to results_fix.json."""
import json, os, time
from multiprocessing import Pool
from dataclasses import asdict
import numpy as np
from sim import Params
from fix import run_fix

SEEDS = [1, 2, 3, 4, 5]
STRUCTS = ["few_large", "medium", "many_small"]
PGRID = [0, 5, 10, 20, 30, 40, 50, 60]

def scenarios():
    S = []
    def add(name, group, **kw):
        S.append(Params(name=name, **kw)); S[-1].__dict__["group"] = group
    for st in STRUCTS:
        for p in PGRID:
            add(f"grid/{st}/priv{p:02d}", "grid", structure=st, private_frac=p / 100)
    base = dict(structure="medium", private_frac=0.05)
    add("sens/adhoc_frac=0.15", "sens", **{**base, "adhoc_frac": 0.15})
    add("sens/small_frac=0.5", "sens", **{**base, "small_frac": 0.5})
    add("sens/priv20_pop_mult=4.0", "sens", structure="medium", private_frac=0.2, private_pop_mult=4.0)
    add("sens/priv50_pop_mult=0.25", "sens", structure="medium", private_frac=0.5, private_pop_mult=0.25)
    add("sens/art_mode=random", "sens", **{**base, "art_mode": "random"})
    add("sens/doc_zipf=0.7", "sens", **{**base, "doc_zipf": 0.7})
    add("mixed/priv15_adhoc10_med", "combo", structure="medium", private_frac=0.15, adhoc_frac=0.10)
    add("combo/worst_case", "combo", structure="many_small", private_frac=0.2, small_frac=0.5, adhoc_frac=0.10)
    add("combo/best_case", "combo", structure="few_large", private_frac=0.0, small_frac=0.10, adhoc_frac=0.0)
    return S

def job(args):
    P, seed = args
    fn = f"runs_fix/{P.name.replace('/', '__')}__s{seed}.json"
    if os.path.exists(fn): return fn
    r = run_fix(P, seed); r["scenario"] = P.name
    json.dump(r, open(fn + ".tmp", "w")); os.replace(fn + ".tmp", fn)
    return fn

def agg(v):
    a = np.array([np.inf if x is None else x for x in v], float)
    return dict(mean=float(a.mean()), min=float(a.min()), max=float(a.max()))

def main():
    os.makedirs("runs_fix", exist_ok=True)
    S = scenarios(); jobs = [(P, s) for P in S for s in SEEDS]; t0 = time.time()
    with Pool(int(os.environ.get("NPROC", 5))) as pool:
        for i, _ in enumerate(pool.imap_unordered(job, jobs)):
            if i % 10 == 0: print(i, len(jobs), round(time.time() - t0), flush=True)
    out = dict(seeds=SEEDS, scenarios={})
    for P in S:
        runs = [json.load(open(f"runs_fix/{P.name.replace('/', '__')}__s{s}.json")) for s in SEEDS]
        m = {}
        for arm in ("base", "A", "B", "C"):
            for k, v in runs[0][arm].items():
                if k == "by_rho":
                    for rho in v:
                        for kk in v[rho]:
                            m[f"A.rho{rho}.{kk}"] = agg([float(r["A"]["by_rho"][rho][kk]) for r in runs])
                elif isinstance(v, (int, float)) or v is None:
                    m[f"{arm}.{k}"] = agg([float(r[arm][k]) if r[arm][k] is not None else None for r in runs])
        for k, v in runs[0]["H"].items():
            if isinstance(v, dict):
                for kk in v: m[f"H.{k}.{kk}"] = agg([float(r["H"][k][kk]) for r in runs])
            else: m[f"H.{k}"] = agg([float(r["H"][k]) for r in runs])
        out["scenarios"][P.name] = dict(group=P.__dict__.get("group"), params=asdict(P), metrics=m,
            art_pass_base_seeds=sum(r["base"]["mass_le3"] < 0.5 for r in runs),
            lmf_pass_seeds=sum(r["A"]["by_rho"]["0.15"]["M2_cost_weighted_unshareable"] < 0.5 for r in runs))
    json.dump(out, open("results_fix.json", "w"), indent=1)
    print("done", round(time.time() - t0))

if __name__ == "__main__":
    main()
