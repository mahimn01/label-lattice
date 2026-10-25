"""Label-Lattice Memoization -- Stage A synthetic org simulator (CPU, numpy only).

Everything is synthetic and parameter-driven. Deterministic given (params, seed).
Principals = users (+ per-user pseudo-principals used for private / ad-hoc ACL entries).
ACL element ids: [0, G) = groups, [G, G+U) = individual users, G+U = padding (zero row).
"""
import hashlib, json, time
from dataclasses import dataclass, asdict, field
import numpy as np

POP = np.array([bin(i).count("1") for i in range(256)], dtype=np.uint8)

STRUCTURES = {
    # n_dept, n_team, n_proj, n_cross, n_role, zipf exponent for group popularity,
    # extra project memberships (Poisson lambda; everyone has >=1), cross-cutting lambda
    "few_large":  dict(n_dept=8,  n_team=40,   n_proj=80,   n_cross=20,  n_role=10,  zipf_g=0.8, proj_lambda=1.0, cross_lambda=0.5),
    "medium":     dict(n_dept=25, n_team=250,  n_proj=1500, n_cross=100, n_role=40,  zipf_g=1.0, proj_lambda=1.5, cross_lambda=1.0),
    "many_small": dict(n_dept=60, n_team=1000, n_proj=6000, n_cross=400, n_role=100, zipf_g=1.0, proj_lambda=2.0, cross_lambda=1.5),
}

@dataclass
class Params:
    name: str = "baseline"
    structure: str = "medium"
    n_users: int = 10000
    n_docs: int = 200000
    n_reads: int = 5_000_000
    n_artifacts: int = 100000
    n_art_reads: int = 1_000_000
    private_frac: float = 0.05      # docs whose ACL is exactly one user
    adhoc_frac: float = 0.03        # docs shared with an explicit list of 2-5 users
    small_frac: float = 0.25        # docs whose ACL is 1-2 project groups (small groups)
    # remaining docs: company 10% / dept 25% / cross 15% / role 5% / team 45%
    private_pop_mult: float = 1.0   # popularity multiplier for private docs (1 = neutral)
    doc_zipf: float = 1.0           # Zipf exponent of document read popularity
    art_zipf: float = 1.0
    art_mode: str = "creator"       # 'creator': inputs drawn from one user's read history; 'random': popularity-weighted random docs
    local_proj_prob: float = 0.65   # prob a project membership is within user's own team

def zipf(n, s):
    w = np.arange(1, n + 1, dtype=np.float64) ** (-s)
    return w / w.sum()

def pick(rng, w_cum, size):
    return np.minimum(np.searchsorted(w_cum, rng.random(size), side="right"), len(w_cum) - 1)

def norm_rows(a, pad):
    """sort each row, drop duplicates (replace with pad), pad at the end."""
    a = np.sort(a, axis=1)
    dup = np.zeros(a.shape, bool)
    dup[:, 1:] = (a[:, 1:] == a[:, :-1]) & (a[:, 1:] != pad)
    a = np.where(dup, pad, a)
    return np.sort(a, axis=1)

# ------------------------------------------------------------------ org
def build_org(P, rng):
    S = STRUCTURES[P.structure]
    U = P.n_users
    nd, nt, npj, nc, nr = S["n_dept"], S["n_team"], S["n_proj"], S["n_cross"], S["n_role"]
    z = S["zipf_g"]
    G = 1 + nd + nt + npj + nc + nr
    team0 = 1 + nd; proj0 = team0 + nt; cross0 = proj0 + npj; role0 = cross0 + nc
    dw = zipf(nd, z)
    user_dept = pick(rng, np.cumsum(dw), U)
    team_dept = np.empty(nt, np.int64)
    team_dept[:nd] = np.arange(nd)
    team_dept[nd:] = pick(rng, np.cumsum(dw), nt - nd)
    tw = zipf(nt, z)[rng.permutation(nt)]
    user_team = np.empty(U, np.int64)
    team_cum_by_dept = {}
    for d in range(nd):
        ts = np.flatnonzero(team_dept == d)
        us = np.flatnonzero(user_dept == d)
        if len(us) == 0:
            continue
        cw = np.cumsum(tw[ts] / tw[ts].sum())
        user_team[us] = ts[pick(rng, cw, len(us))]
    user_dept = team_dept[user_team]     # dept implied by team (hierarchy)
    pw = zipf(npj, z)[rng.permutation(npj)]
    proj_team = pick(rng, np.cumsum(tw / tw.sum()), npj)
    team_projs = [np.flatnonzero(proj_team == t) for t in range(nt)]
    team_pcum = [np.cumsum(pw[p] / pw[p].sum()) if len(p) else None for p in team_projs]
    pglob = np.cumsum(pw / pw.sum())
    k = 1 + rng.poisson(S["proj_lambda"], U)
    pairs_u, pairs_g = [], []
    ut = user_team.tolist()
    rl = rng.random(int(k.sum())); ru = rng.random(int(k.sum()))
    i = 0
    for u in range(U):
        mem = set()
        for _ in range(int(k[u])):
            t = ut[u]
            if rl[i] < P.local_proj_prob and team_pcum[t] is not None:
                p = team_projs[t][min(int(np.searchsorted(team_pcum[t], ru[i], "right")), len(team_projs[t]) - 1)]
            else:
                p = min(int(np.searchsorted(pglob, ru[i], "right")), npj - 1)
            mem.add(int(p)); i += 1
        for p in mem:
            pairs_u.append(u); pairs_g.append(proj0 + p)
    pairs_u = [np.array(pairs_u, np.int64)]; pairs_g = [np.array(pairs_g, np.int64)]
    ar = np.arange(U)
    pairs_u.append(ar); pairs_g.append(np.zeros(U, np.int64))            # company
    pairs_u.append(ar); pairs_g.append(1 + user_dept)                    # dept
    pairs_u.append(ar); pairs_g.append(team0 + user_team)                # team
    cw_c = np.cumsum(zipf(nc, z)[rng.permutation(nc)])
    kc = rng.poisson(S["cross_lambda"], U)
    cu = np.repeat(ar, kc)
    pairs_u.append(cu); pairs_g.append(cross0 + pick(rng, cw_c, len(cu)))
    rw = zipf(nr, z)[rng.permutation(nr)]
    pairs_u.append(ar); pairs_g.append(role0 + pick(rng, np.cumsum(rw), U))
    pu = np.concatenate(pairs_u); pg = np.concatenate(pairs_g)
    key = np.unique(pu * G + pg)
    pu, pg = key // G, key % G
    NB = ((U + 63) // 64) * 8         # bytes per bitset, multiple of 8
    B = np.zeros((G + U + 1, NB), np.uint8)
    mask = (128 >> (pu & 7)).astype(np.uint8)
    np.bitwise_or.at(B, (pg, pu >> 3), mask)
    B[G + ar, ar >> 3] = (128 >> (ar & 7)).astype(np.uint8)
    act = rng.lognormal(0.0, 1.0, U); act /= act.sum()
    org = dict(U=U, G=G, NB=NB, B=B, pu=pu, pg=pg, act=act, pad=G + U,
               gsize=np.bincount(pg, minlength=G),
               off=dict(company=0, dept=1, team=team0, proj=proj0, cross=cross0, role=role0),
               n=dict(dept=nd, team=nt, proj=npj, cross=nc, role=nr),
               w=dict(dept=dw, team=tw / tw.sum(), proj=pw / pw.sum(), cross=zipf(nc, z)[rng.permutation(nc)] if False else np.diff(np.r_[0, cw_c]), role=rw))
    return org

# ------------------------------------------------------------------ audiences
class AudStore:
    """Deduplicates audience bitsets (canonical label = the audience set) in chunks."""
    def __init__(self, NB, seed=12345):
        r = np.random.default_rng(seed)
        self.R = r.integers(1, 2**63, NB // 8, dtype=np.uint64) * np.uint64(2) + np.uint64(1)
        self.chunks = []; self.n_items = 0
    def hash(self, bits):
        return (np.ascontiguousarray(bits).view(np.uint64) * self.R).sum(axis=1, dtype=np.uint64)
    def add(self, bits):
        h = self.hash(bits)
        uh, first, inv = np.unique(h, return_index=True, return_inverse=True)
        self.chunks.append((uh, bits[first].copy(), inv.reshape(-1), self.n_items))
        self.n_items += len(bits)
    def finalize(self):
        allh = np.concatenate([c[0] for c in self.chunks])
        allb = np.concatenate([c[1] for c in self.chunks])
        uh, first, inv = np.unique(allh, return_index=True, return_inverse=True)
        inv = inv.reshape(-1)
        bits = allb[first]
        item_aud = np.empty(self.n_items, np.int64)
        base = 0
        for h, b, linv, n0 in self.chunks:
            item_aud[n0:n0 + len(linv)] = inv[base:base + len(h)][linv]
            base += len(h)
        size = np.zeros(len(bits), np.int64)
        for s in range(0, len(bits), 20000):
            size[s:s + 20000] = POP[bits[s:s + 20000]].sum(axis=1, dtype=np.int64)
        self.chunks = None
        return item_aud, bits, size

def audience_of_acl_rows(org, rows, chunk=20000):
    st = AudStore(org["NB"])
    B = org["B"]
    for s in range(0, len(rows), chunk):
        r = rows[s:s + chunk]
        aud = B[r[:, 0]].copy()
        for j in range(1, r.shape[1]):
            aud |= B[r[:, j]]
        st.add(aud)
    return st.finalize()

# ------------------------------------------------------------------ documents
def build_docs(P, org, rng):
    ND, U, G, pad = P.n_docs, org["U"], org["G"], org["pad"]
    off, n, w = org["off"], org["n"], org["w"]
    act = org["act"]
    acl = np.full((ND, 5), pad, np.int64)
    u = rng.random(ND)
    c1 = P.private_frac; c2 = c1 + P.adhoc_frac; c3 = c2 + P.small_frac
    typ = np.full(ND, 3, np.int8)   # 3 = broad/structural
    typ[u < c3] = 2; typ[u < c2] = 1; typ[u < c1] = 0
    sub = rng.choice(5, ND, p=[0.10, 0.25, 0.15, 0.05, 0.45])   # company,dept,cross,role,team
    second = rng.random(ND)
    # per-user docs-owned weights heavy tailed
    ow = rng.lognormal(0, 1.0, U); ow /= ow.sum()
    idx = np.flatnonzero(typ == 0)
    acl[idx, 0] = G + pick(rng, np.cumsum(ow), len(idx))
    idx = np.flatnonzero(typ == 1)
    k = rng.integers(2, 6, len(idx))
    cu = np.cumsum(act)
    pk = G + pick(rng, cu, (len(idx), 5))
    pk = np.where(np.arange(5)[None, :] < k[:, None], pk, pad)
    acl[idx, :] = pk
    def fill(mask, kind, p2):
        ii = np.flatnonzero(mask)
        if len(ii) == 0: return
        cw = np.cumsum(w[kind])
        acl[ii, 0] = off[kind] + pick(rng, cw, len(ii))
        s2 = second[ii] < p2
        acl[ii, 1] = np.where(s2, off[kind] + pick(rng, cw, len(ii)), pad)
    fill(typ == 2, "proj", 0.30)
    b = typ == 3
    acl[np.flatnonzero(b & (sub == 0)), 0] = off["company"]
    fill(b & (sub == 1), "dept", 0.20)
    fill(b & (sub == 2), "cross", 0.30)
    fill(b & (sub == 3), "role", 0.0)
    fill(b & (sub == 4), "team", 0.25)
    acl = norm_rows(acl, pad)
    uacl, acl_id = np.unique(acl, axis=0, return_inverse=True)
    acl_id = acl_id.reshape(-1)
    aud_of_acl, aud_bits, aud_size = audience_of_acl_rows(org, uacl)
    doc_aud = aud_of_acl[acl_id]
    return dict(typ=typ, acl=acl, uacl=uacl, acl_id=acl_id, doc_aud=doc_aud,
                aud_bits=aud_bits, aud_size=aud_size, doc_size=aud_size[doc_aud])

# ------------------------------------------------------------------ reads
def sample_readers(item_aud, aud_bits, items, act, rng, U):
    a = item_aud[items]
    order = np.argsort(a, kind="stable")
    sa = a[order]
    cuts = np.flatnonzero(np.diff(sa)) + 1
    starts = np.r_[0, cuts]; ends = np.r_[cuts, len(sa)]
    users = np.empty(len(items), np.int32)
    for s, e in zip(starts.tolist(), ends.tolist()):
        idx = np.flatnonzero(np.unpackbits(aud_bits[sa[s]])[:U])
        if len(idx) == 1:
            users[order[s:e]] = idx[0]; continue
        cw = np.cumsum(act[idx])
        pos = np.minimum(np.searchsorted(cw, rng.random(e - s) * cw[-1], side="right"), len(idx) - 1)
        users[order[s:e]] = idx[pos]
    return users

EDGES = [1, 2, 3, 10, 100, 1000, 5000]
def hist_edges(U):
    return EDGES + [U - 1, U]
def hist_labels(U):
    return ["1", "2", "3", "4-10", "11-100", "101-1000", "1001-5000", f"5001-{U-1}", f"{U} (all)"]

def read_metrics(users, items, n_items, item_size, U):
    N = len(items)
    key = users.astype(np.int64) * n_items + items
    uk = np.unique(key)
    P_pairs = len(uk)
    readers = np.bincount(uk % n_items, minlength=n_items)
    reads = np.bincount(items, minlength=n_items)
    D = int(np.count_nonzero(readers))
    sz = item_size
    m = lambda mask: float(reads[mask].sum() / N)
    he = hist_edges(U)
    bins = np.minimum(np.searchsorted(he, sz, side="left"), len(he) - 1)
    mass_hist = (np.bincount(bins, weights=reads, minlength=len(he)) / N).tolist()
    return dict(
        n_reads=N, distinct_items_read=D, distinct_user_item_pairs=int(P_pairs),
        potential_shareable_mass=m(sz >= 2),
        realized_shared_mass=m(readers >= 2),
        mass_aud_le1=m(sz <= 1), mass_aud_le3=m(sz <= 3), mass_aud_le10=m(sz <= 10), mass_aud_le100=m(sz <= 100),
        hit_rate_per_user_cache=1 - P_pairs / N,
        hit_rate_shared_lazy=1 - D / N,
        hit_rate_shared_eager=1.0,
        storage_entries_per_user=int(P_pairs), storage_entries_shared=D,
        storage_ratio_per_user_over_shared=P_pairs / max(D, 1),
        compute_ratio_per_user_over_shared=P_pairs / max(D, 1),
        read_mass_by_audience_bin=mass_hist,
        mean_audience_read_weighted=float((reads * sz).sum() / N),
        median_audience_read_weighted=float(weighted_quantile(sz, reads, 0.5)),
    )

def weighted_quantile(x, w, q):
    o = np.argsort(x, kind="stable"); cw = np.cumsum(w[o]); return x[o][np.searchsorted(cw, q * cw[-1])]

def label_dist(aud_size_unique, U):
    """distribution of principals-per-label over distinct labels (count of labels)."""
    he = hist_edges(U)
    bins = np.minimum(np.searchsorted(he, aud_size_unique, side="left"), len(he) - 1)
    return dict(count_by_bin=np.bincount(bins, minlength=len(he)).tolist(),
                pct={str(q): float(np.percentile(aud_size_unique, q)) for q in (10, 25, 50, 75, 90, 99)},
                mean=float(aud_size_unique.mean()), max=int(aud_size_unique.max()),
                frac_labels_le3=float((aud_size_unique <= 3).mean()))

# ------------------------------------------------------------------ artifacts
ART_K = np.arange(2, 9)
ART_KP = np.array([0.30, 0.25, 0.15, 0.10, 0.08, 0.07, 0.05])

def build_artifacts(P, org, docs, doc_cw, user_r, doc_r, rng):
    NA, U, pad = P.n_artifacts, org["U"], org["pad"]
    k = rng.choice(ART_K, NA, p=ART_KP)
    if P.art_mode == "creator":
        order = np.argsort(user_r, kind="stable")
        sdocs = doc_r[order]
        cnt = np.bincount(user_r, minlength=U)
        start = np.r_[0, np.cumsum(cnt)[:-1]]
        ok = np.flatnonzero(cnt >= 2)
        cw = np.cumsum(cnt[ok] / cnt[ok].sum())
        creators = ok[pick(rng, cw, NA)]
        pos = start[creators][:, None] + np.floor(rng.random((NA, 8)) * cnt[creators][:, None]).astype(np.int64)
        inp = sdocs[pos]
    elif P.art_mode == "random":
        inp = pick(rng, doc_cw, (NA, 8))
    else:
        raise ValueError(P.art_mode)
    inp = np.where(np.arange(8)[None, :] < k[:, None], inp, inp[:, [0]]).astype(np.int64)
    aud_bits = docs["aud_bits"]; doc_aud = docs["doc_aud"]
    st = AudStore(org["NB"])
    for s in range(0, NA, 10000):
        ids = doc_aud[inp[s:s + 10000]]
        bits = aud_bits[ids[:, 0]].copy()
        for j in range(1, 8):
            bits &= aud_bits[ids[:, j]]
        st.add(bits)
    art_aud, abits, asize_u = st.finalize()
    art_size = asize_u[art_aud]
    # symbolic label = set of distinct input ACL ids
    sym = norm_rows(docs["acl_id"][inp], -1)
    # norm_rows uses pad=-1 semantic: dups -> -1 ; sort puts -1 first, fine for uniqueness
    n_sym = len(np.unique(sym, axis=0))
    din = np.sort(inp, axis=1)
    n_distinct_inputs = 1 + (din[:, 1:] != din[:, :-1]).sum(axis=1)
    min_in = docs["doc_size"][inp].min(axis=1)
    return dict(inputs=inp, aud=art_aud, bits=abits, size_u=asize_u, size=art_size, n_sym=n_sym,
                mean_distinct_inputs=float(n_distinct_inputs.mean()),
                frac_empty=float((art_size == 0).mean()),
                frac_narrower_than_min_input=float((art_size < min_in).mean()),
                mean_shrink_ratio=float(np.mean(art_size[art_size > 0] / min_in[art_size > 0])),
                median_shrink_ratio=float(np.median(art_size[art_size > 0] / min_in[art_size > 0])))

# ------------------------------------------------------------------ run
def run(P, seed):
    t0 = time.time()
    ss = np.random.SeedSequence([seed, 20261025])
    r_org, r_doc, r_read, r_art, r_aread, r_rs = [np.random.default_rng(s) for s in ss.spawn(6)]
    U = P.n_users
    org = build_org(P, r_org)
    docs = build_docs(P, org, r_doc)
    ND = P.n_docs
    # signatures
    G = org["G"]; pu, pg = org["pu"], org["pg"]
    Rg = np.random.default_rng(777).integers(1, 2**63, G, dtype=np.uint64)
    def sigs(sel):
        s = np.zeros(U, np.uint64)
        np.add.at(s, pu[sel], Rg[pg[sel]])
        return s
    sig_all = sigs(np.ones(len(pu), bool))
    used = np.zeros(G, bool); a = docs["uacl"]; used[a[a < G]] = True
    sig_used = sigs(used[pg])
    grant_users = np.unique(np.concatenate([docs["acl"][docs["typ"] <= 1].ravel() - G]))
    grant_users = grant_users[(grant_users >= 0) & (grant_users < U)]
    has_grant = np.zeros(U, bool); has_grant[grant_users] = True
    n_sig_all = len(np.unique(sig_all)); n_sig_used = len(np.unique(sig_used))
    n_sig_grants = len(np.unique(sig_used[~has_grant])) + int(has_grant.sum())
    _, inv, cnts = np.unique(sig_all, return_inverse=True, return_counts=True)
    sig_stats = dict(distinct_group_signatures=n_sig_all,
                     distinct_signatures_acl_relevant_groups_only=n_sig_used,
                     distinct_signatures_incl_individual_grants=n_sig_grants,
                     frac_users_in_singleton_signature=float((cnts[inv.reshape(-1)] == 1).mean()),
                     largest_signature_class=int(cnts.max()),
                     users_with_individual_grant=int(has_grant.sum()),
                     mean_groups_per_user=float(len(pu) / U))
    # doc reads
    rank = r_rs.permutation(ND)
    mult = np.where(docs["typ"] == 0, P.private_pop_mult, 1.0)
    wd = (rank + 1.0) ** (-P.doc_zipf) * mult * (docs["doc_size"] > 0)
    doc_cw = np.cumsum(wd / wd.sum())
    doc_r = pick(r_read, doc_cw, P.n_reads).astype(np.int64)
    user_r = sample_readers(docs["doc_aud"], docs["aud_bits"], doc_r, org["act"], r_read, U)
    dm = read_metrics(user_r, doc_r, ND, docs["doc_size"], U)
    # type breakdown of read mass
    dm["frac_docs_empty_audience"] = float((docs["doc_size"] == 0).mean())
    tm = np.bincount(docs["typ"][doc_r], minlength=4) / len(doc_r)
    dm["read_mass_by_doc_type"] = dict(private=float(tm[0]), adhoc=float(tm[1]), small_group=float(tm[2]), broad=float(tm[3]))
    # artifacts
    art = build_artifacts(P, org, docs, doc_cw, user_r, doc_r, r_art)
    NA = P.n_artifacts
    wa = (r_rs.permutation(NA) + 1.0) ** (-P.art_zipf) * (art["size"] > 0)
    art_cw = np.cumsum(wa / wa.sum())
    art_r = pick(r_aread, art_cw, P.n_art_reads).astype(np.int64)
    auser = sample_readers(art["aud"], art["bits"], art_r, org["act"], r_aread, U)
    am = read_metrics(auser, art_r, NA, art["size"], U)
    out = dict(
        params=asdict(P), seed=seed, seconds=None,
        signatures=sig_stats,
        doc_labels=dict(distinct_acl_sets=int(len(docs["uacl"])), distinct_audiences=int(len(docs["aud_size"])),
                        audience_dist=label_dist(docs["aud_size"], U)),
        artifact_labels=dict(distinct_symbolic_input_sets=int(art["n_sym"]),
                             distinct_audiences=int(len(art["size_u"])),
                             distinct_audiences_nonempty=int((art["size_u"] > 0).sum()),
                             audience_dist=label_dist(art["size_u"][art["size_u"] > 0], U),
                             mean_distinct_inputs=art["mean_distinct_inputs"], frac_empty=art["frac_empty"],
                             frac_narrower_than_min_input=art["frac_narrower_than_min_input"],
                             mean_shrink_ratio=art["mean_shrink_ratio"], median_shrink_ratio=art["median_shrink_ratio"]),
        doc_reads=dm, artifact_reads=am,
        group_sizes=dict(max=int(org["gsize"][1:].max()), median=float(np.median(org["gsize"][1:])),
                         n_groups=int(G)),
        hist_labels=hist_labels(U),
    )
    out["falsifier"] = dict(
        threshold=0.5,
        docs_mass_le3=dm["mass_aud_le3"], docs_pass=bool(dm["mass_aud_le3"] < 0.5),
        artifacts_mass_le3=am["mass_aud_le3"], artifacts_pass=bool(am["mass_aud_le3"] < 0.5))
    out["seconds"] = round(time.time() - t0, 1)
    return out

if __name__ == "__main__":
    import sys
    P = Params()
    if "--quick" in sys.argv:
        P.n_users, P.n_docs, P.n_reads, P.n_artifacts, P.n_art_reads = 2000, 40000, 500000, 20000, 200000
    import resource
    r = run(P, 1)
    json.dump(r, open("/tmp/ll_one.json", "w"), indent=1)
    print("seconds", r["seconds"], "peak_rss_MB", resource.getrusage(resource.RUSAGE_SELF).ru_maxrss // 1024)
