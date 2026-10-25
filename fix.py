"""Lazy-Meet Factoring (LMF) and comparison arms for derived-artifact label-lattice memoization.

Reuses sim.py (imported unchanged). `run_fix` replays the exact RNG pipeline of sim.run so the
BASELINE numbers reproduce results.json bit for bit, then evaluates fix arms on the same artifacts
and the same artifact reads.

Arms (artifact side):
  base : monolithic artifact, label = intersection of input audiences (the existing design).
  A    : LMF. Expensive per-chunk components, each labelled by that ONE doc's ACL, cached once per
         (doc, version). A cheap join composes them at read time; the join is gated on entitlement to
         EVERY input. Composite cached under the intersection label (tier 2) but it is cheap.
  B    : group-closure cover. Round the intersection label DOWN to a cover by existing org groups that
         are fully contained in it (+ leftover individual users). Same monolithic content computed once
         per cover class.
  C    : class-partial. Partials per (artifact, doc-ACL class), joined at read. No cross-artifact reuse.

Cost model (chunk units): computing one chunk component = 1; a monolithic artifact over k distinct
inputs = k; the join (reduce / cross-attention patch) costs RHO*k and its output occupies RHO*k.
"""
import json, time
import numpy as np
from sim import (Params, build_org, build_docs, build_artifacts, sample_readers, read_metrics,
                 pick, POP)
from dataclasses import asdict

RHO = 0.15           # join cost / output size as a fraction of the chunk work it joins (assumed; swept)
RHOS = (0.05, 0.15, 0.30, 1.00)

def _expand_components(art, art_r, auser):
    s = np.sort(art["inputs"], axis=1)
    valid = np.ones(s.shape, bool); valid[:, 1:] = s[:, 1:] != s[:, :-1]
    kd = valid.sum(axis=1)
    rows = s[art_r]; v = valid[art_r]
    items = rows[v]
    users = np.broadcast_to(auser[:, None], v.shape)[v]
    return s, valid, kd, items, users

def arm_cover(org, docs, art, s, valid, kd, art_r, auser, ra):
    """Arm B. Returns per-read effective class size and distinct (artifact, class) keys."""
    G, U, NB = org["G"], org["U"], org["NB"]
    B = org["B"]; padg = G + U
    NA = len(art["aud"])
    dsize = docs["doc_size"]
    # candidate groups: ACL groups of the narrowest input (any group inside the intersection must be
    # inside every input's audience; we take the narrowest input's named groups as the candidate pool)
    j = np.argmin(np.where(valid, dsize[s], 1 << 40), axis=1)
    narrow = s[np.arange(NA), j]
    cand = docs["uacl"][docs["acl_id"][narrow]]            # (NA,5) ACL elements (pad = G+U)
    cand = np.where(cand < G, cand, padg)
    chosen = np.full((NA, 5), padg, np.int64)
    viol = 0
    for lo in range(0, NA, 4000):
        hi = min(NA, lo + 4000)
        I = art["bits"][art["aud"][lo:hi]]                  # (n,NB) intersection audience
        c = cand[lo:hi]
        order = np.argsort(-np.where(c < G, org["gsize"][np.minimum(c, G - 1)], -1), axis=1, kind="stable")
        c = np.take_along_axis(c, order, axis=1)
        union = np.zeros_like(I)
        for jj in range(5):
            g = c[:, jj]
            Bg = B[g]                                        # pad row is all zero
            inside = ((Bg & ~I) == 0).all(axis=1) & (g < G)
            adds = ((Bg & ~union) != 0).any(axis=1)
            take = inside & adds
            chosen[lo:hi, jj] = np.where(take, g, padg)
            union = np.where(take[:, None], union | Bg, union)
    # independent check that every chosen group is inside the intersection (security invariant)
    for lo in range(0, NA, 4000):
        hi = min(NA, lo + 4000)
        I = art["bits"][art["aud"][lo:hi]]
        for jj in range(5):
            g = chosen[lo:hi, jj]
            viol += int((((B[g] & ~I) != 0).any(axis=1) & (g < G)).sum())
    # per-read class
    cs = chosen[art_r]                                       # (N,5)
    ub = (auser >> 3).astype(np.int64); bit = (7 - (auser & 7)).astype(np.uint8)
    inG = np.zeros(cs.shape, bool)
    for jj in range(5):
        inG[:, jj] = ((B[cs[:, jj], ub] >> bit) & 1).astype(bool)
    first = np.where(inG.any(axis=1), inG.argmax(axis=1), -1)
    gid = np.where(first >= 0, cs[np.arange(len(first)), np.maximum(first, 0)], G + auser.astype(np.int64))
    eff = np.where(first >= 0, org["gsize"][np.minimum(gid, G - 1)], 1)
    key = art_r.astype(np.int64) * (G + U + 1) + gid
    uk = np.unique(key)
    return eff, uk, viol, (G + U + 1), chosen

def run_fix(P, seed, rhos=RHOS):
    t0 = time.time()
    ss = np.random.SeedSequence([seed, 20261025])
    r_org, r_doc, r_read, r_art, r_aread, r_rs = [np.random.default_rng(s) for s in ss.spawn(6)]
    U = P.n_users
    org = build_org(P, r_org); docs = build_docs(P, org, r_doc); ND = P.n_docs
    rank = r_rs.permutation(ND)
    mult = np.where(docs["typ"] == 0, P.private_pop_mult, 1.0)
    wd = (rank + 1.0) ** (-P.doc_zipf) * mult * (docs["doc_size"] > 0)
    doc_cw = np.cumsum(wd / wd.sum())
    doc_r = pick(r_read, doc_cw, P.n_reads).astype(np.int64)
    user_r = sample_readers(docs["doc_aud"], docs["aud_bits"], doc_r, org["act"], r_read, U)
    dm = read_metrics(user_r, doc_r, ND, docs["doc_size"], U)
    art = build_artifacts(P, org, docs, doc_cw, user_r, doc_r, r_art)
    NA = P.n_artifacts
    wa = (r_rs.permutation(NA) + 1.0) ** (-P.art_zipf) * (art["size"] > 0)
    art_cw = np.cumsum(wa / wa.sum())
    art_r = pick(r_aread, art_cw, P.n_art_reads).astype(np.int64)
    auser = sample_readers(art["aud"], art["bits"], art_r, org["act"], r_aread, U)
    am = read_metrics(auser, art_r, NA, art["size"], U)
    N = len(art_r)

    s, valid, kd, items, users = _expand_components(art, art_r, auser)
    ra = np.bincount(art_r, minlength=NA)
    asz = art["size"]
    kdf = kd.astype(np.float64)
    demand = float((ra * kdf).sum())
    # ---- baseline costs (chunk units)
    pair = np.unique(auser.astype(np.int64) * NA + art_r)
    pair_art = pair % NA
    cost_per_user = float(kdf[pair_art].sum()); entries_per_user = len(pair)
    Dart = np.flatnonzero(ra > 0)
    cost_old_shared = float(kdf[Dart].sum()); entries_old_shared = len(Dart)
    out = dict(params=asdict(P), seed=seed)
    out["base"] = dict(mass_le3=am["mass_aud_le3"], hit_rate_per_user=am["hit_rate_per_user_cache"],
                       hit_rate_shared=am["hit_rate_shared_lazy"], entries_per_user=entries_per_user,
                       entries_shared=entries_old_shared, units_per_user=cost_per_user,
                       units_shared=cost_old_shared, units_nocache=demand,
                       storage_units_per_user=cost_per_user, storage_units_shared=cost_old_shared,
                       mean_distinct_inputs=float(kd.mean()))
    # ---- arm A: LMF
    cm = read_metrics(users, items, ND, docs["doc_size"], U)      # component-level reads
    n3 = (valid & (docs["doc_size"][s] <= 3)).sum(axis=1).astype(np.float64)
    small_art = (asz <= 3).astype(np.float64)
    D_comp = cm["distinct_items_read"]
    A = dict(M1_comp_mass_le3=cm["mass_aud_le3"], comp_mass_le10=cm["mass_aud_le10"],
             comp_realized_shared=cm["realized_shared_mass"],
             comp_hit_rate_per_user=cm["hit_rate_per_user_cache"], comp_hit_rate_shared=cm["hit_rate_shared_lazy"],
             entries_components=D_comp, entries_composites=len(Dart),
             entries_total=D_comp + len(Dart), entries_composites_admit2=int((ra >= 2).sum()),
             entries_total_admit2=D_comp + int((ra >= 2).sum()), comp_pairs_per_user=cm["distinct_user_item_pairs"],
             doc_mass_le3_reference=dm["mass_aud_le3"], by_rho={})
    for rho in rhos:
        join = rho * float(kdf[Dart].sum())
        units = D_comp + join
        m2 = float((ra * (n3 + rho * kdf * small_art)).sum() / (demand * (1 + rho)))
        A["by_rho"][str(rho)] = dict(
            M2_cost_weighted_unshareable=m2, pass_=bool(m2 < 0.5),
            units=units, units_vs_per_user=units / cost_per_user, units_vs_old_shared=units / cost_old_shared,
            units_vs_nocache=units / demand,
            storage_units=D_comp + join, storage_vs_per_user=(D_comp + join) / cost_per_user,
            entries_ratio_per_user_over_lmf=entries_per_user / (D_comp + len(Dart)),
            work_hit_rate=1 - units / (demand * (1 + rho)))
    # break-even rho where M2 = 0.5 (join cost at which LMF stops passing)
    a_ = float((ra * n3).sum() / demand); b_ = float((ra * kdf * small_art).sum() / demand)
    # M2(rho) = (a + rho b)/(1+rho) = 0.5  ->  rho = (0.5 - a)/(b - 0.5)
    A["breakeven_rho"] = float((0.5 - a_) / (b_ - 0.5)) if b_ > 0.5 and a_ < 0.5 else (None if a_ >= 0.5 else float("inf"))
    A["M1_per_artifact_read_avg"] = a_; A["join_share_le3"] = b_
    A["M1_pass"] = bool(cm["mass_aud_le3"] < 0.5)
    out["A"] = A
    # ---- arm H: narrow-only LMF (hybrid). Artifacts whose intersection audience is <= T go through LMF;
    # wider ones stay monolithic (lossless, no join) under their intersection label.
    H = {}
    for T in (3, 10):
        narrow = asz <= T
        rn = narrow[art_r]
        _, _, _, items_n, users_n = _expand_components(art, art_r[rn], auser[rn])
        Dn = len(np.unique(items_n))
        Dn_art = Dart[narrow[Dart]]; Dw_art = Dart[~narrow[Dart]]
        for rho in rhos:
            units = float(kdf[Dw_art].sum()) + Dn + rho * float(kdf[Dn_art].sum())
            denom = float((ra * kdf * np.where(narrow, 1 + rho, 1.0)).sum())
            unsh = float((ra * np.where(narrow, n3 + rho * kdf * small_art, 0.0)).sum()) / denom
            H[f"T{T}.rho{rho}"] = dict(M2=unsh, units=units, units_vs_per_user=units / cost_per_user,
                                       units_vs_old_shared=units / cost_old_shared)
        H[f"T{T}.lmf_read_share"] = float(rn.mean())
        H[f"T{T}.entries"] = int(len(Dw_art) + Dn + len(Dn_art))
    out["H"] = H
    # ---- arm B: group-closure cover
    eff, uk, viol, M, _chosen = arm_cover(org, docs, art, s, valid, kd, art_r, auser, ra)
    ak = uk // M
    B_ = dict(mass_le3=float((eff <= 3).mean()), mass_le10=float((eff <= 10).mean()),
              hit_rate=1 - len(uk) / N, entries=len(uk), units=float(kdf[ak].sum()),
              units_vs_per_user=float(kdf[ak].sum()) / cost_per_user,
              units_vs_old_shared=float(kdf[ak].sum()) / cost_old_shared,
              entries_ratio_per_user_over_B=entries_per_user / len(uk), cover_violations=viol,
              pass_=bool((eff <= 3).mean() < 0.5))
    out["B"] = B_
    # ---- arm C: class-partial
    da = np.sort(docs["doc_aud"][s], axis=1)
    npart = 1 + (da[:, 1:] != da[:, :-1]).sum(axis=1)
    C = dict(M1_mass_le3=cm["mass_aud_le3"], entries=int(npart[Dart].sum()) + len(Dart))
    for rho in rhos:
        C[f"units_rho{rho}"] = float(kdf[Dart].sum() + rho * npart[Dart].sum())
    out["C"] = C
    out["seconds"] = round(time.time() - t0, 1)
    return out

if __name__ == "__main__":
    import sys
    P = Params(structure="medium", private_frac=0.05)
    if "--quick" in sys.argv:
        P.n_users, P.n_docs, P.n_reads, P.n_artifacts, P.n_art_reads = 2000, 40000, 500000, 20000, 200000
    r = run_fix(P, 1)
    print(json.dumps(r, indent=1))
