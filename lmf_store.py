"""Reference model of Lazy-Meet Factoring (LMF) with provenance tracking, used by test_lmf.py.

Design (see FIX.md):
  * COMPONENT = expensive per-chunk work (KV segment / chunk note / claim list). Pure function of ONE
    document's content at one version. Label = that document's ACL alone. Cached once per (doc, version).
  * COMPOSITE = cheap join of the components of an artifact's inputs (summary-of-notes, KV patch, claim
    merge). Label = intersection of the inputs' ACLs, but this is only a GATE evaluated at read time,
    never baked into expensive work. Cached under (artifact, versions) for reuse.
  * Every read passes the gate first: the principal must be entitled to EVERY provenance doc. The gate runs
    before any cache lookup, so a refused principal causes no cache access (no hit/miss or timing oracle
    on the shared store from non-entitled principals).
  * Entitlement decisions are cached under a lease. ACL changes push-invalidate leases (no recompute);
    if the push is delayed, staleness is bounded by the lease. Content change or deletion tombstones the
    component and every composite that contains it.
Content strings carry a marker "[[doc:<id>@<ver>]]" per source so tests can scan for leaked sources.
"""
from lattice import Clock, AclService, Refused

class LmfStore:
    def __init__(self, acl, clock, lease_s=30.0, push=True):
        self.acl, self.clock, self.lease_s, self.push = acl, clock, lease_s, push
        self.docs = {}          # doc -> dict(version, text, deleted)
        self.comp = {}          # (doc, version) -> dict(prov, content)
        self.compos = {}        # art_id -> dict(inputs, key, prov, content, tombstoned)
        self.lease = {}         # (user, kind, id) -> (expires_at)
        self.pending = []
        self.cache_lookups = 0  # counts accesses to the SHARED caches (comp/compos); refused reads must not move it
        self.n_comp_compute = 0; self.n_join_compute = 0
        acl.listeners.append(self._on_acl_change)
    # ---- documents
    def put_doc(self, doc, text="text"):
        prev = self.docs.get(doc)
        self.docs[doc] = dict(version=(prev["version"] + 1 if prev else 1), text=text, deleted=False)
        if prev:   # content change: composites that contain the old version are no longer valid
            self._tombstone_composites({doc})
    def delete_doc(self, doc):
        self.docs[doc]["deleted"] = True
        self._tombstone_composites({doc})
    # ---- gate
    def _entitled(self, user, docs):
        return all(self.acl.can_read_doc(user, d) for d in docs)
    def _gate(self, user, kind, ident, docs):
        """Entitlement check (leased). Runs BEFORE any shared-cache access. Raises Refused identically for
        'not entitled', 'no such artifact' style probes would be a different story; here all refusals look the same."""
        now = self.clock.now()
        key = (user, kind, ident)
        exp = self.lease.get(key)
        if exp is not None and now < exp:
            return
        self.lease.pop(key, None)
        if not self._entitled(user, docs):
            raise Refused("refused")
        self.lease[key] = now + self.lease_s
    # ---- components
    def _component(self, doc):
        d = self.docs[doc]
        if d["deleted"]:
            raise Refused("refused")
        self.cache_lookups += 1
        k = (doc, d["version"])
        if k not in self.comp:
            self.n_comp_compute += 1
            # a component is a pure function of ONE doc's text (+ public prompt). Provenance = {doc}.
            self.comp[k] = dict(prov=frozenset({doc}), content=f"[[doc:{doc}@{d['version']}]]")
        return self.comp[k]
    def read_component(self, user, doc):
        self._gate(user, "comp", doc, [doc])
        return self._component(doc)
    # ---- composites
    def compose(self, user, art_id, input_docs):
        inputs = tuple(sorted(set(input_docs)))
        self._gate(user, "compos", (art_id, inputs), inputs)        # must be entitled to EVERY input
        self.cache_lookups += 1
        c = self.compos.get(art_id)
        ver = tuple(self.docs[d]["version"] for d in inputs)
        if c is None or c["tombstoned"] or c["inputs"] != inputs or c["ver"] != ver:
            parts = [self._component(d) for d in inputs]            # expensive part: cached per doc
            self.n_join_compute += 1
            prov = frozenset().union(*[p["prov"] for p in parts])
            self.compos[art_id] = c = dict(inputs=inputs, ver=ver, prov=prov, tombstoned=False,
                                           content="join(" + ",".join(p["content"] for p in parts) + ")")
        assert c["prov"] == frozenset(inputs)
        # defence in depth: re-check the recorded provenance (not just the requested inputs) under the same lease rules
        self._gate(user, "prov", (art_id, ver), sorted(c["prov"]))
        return c
    # ---- invalidation
    def _tombstone_composites(self, docs):
        for c in self.compos.values():
            if set(c["inputs"]) & set(docs):
                c["tombstoned"] = True
        self._drop_leases(docs)
    def _drop_leases(self, docs):
        docs = set(docs)
        def hit(key):
            _, kind, ident = key
            if kind == "comp": return ident in docs
            if kind == "compos": return bool(set(ident[1]) & docs)
            if kind == "prov":
                c = self.compos.get(ident[0])
                return bool(c and set(c["inputs"]) & docs)
            return False
        self.lease = {k: v for k, v in self.lease.items() if not hit(k)}
    def _on_acl_change(self, docs, epoch):
        if self.push: self._drop_leases(docs)       # ACL change: gate re-evaluated, NOTHING recomputed
        else: self.pending.append((docs, epoch))
    def deliver_pending(self):
        for docs, _ in self.pending: self._drop_leases(docs)
        self.pending = []
