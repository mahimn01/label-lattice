"""Minimal reference model of the report's Label-Lattice mechanics, used for the revocation test.

- AclService: group membership + per-document ACLs, with a monotonically increasing ACL epoch.
- ArtifactStore: artifacts keyed by (artifact_id, version); label = the list of input-doc ACLs
  (audience = INTERSECTION of the inputs' audiences). Every read checks tombstones and an
  entitlement lease. With push invalidation, ACL changes tombstone dependants immediately; without it
  (push channel delayed / partitioned), a cached entitlement decision is trusted only until its lease expires,
  so staleness is bounded by the lease.
All time is an explicit simulated clock (deterministic).
"""

class Clock:
    def __init__(self, t=0.0): self.t = float(t)
    def now(self): return self.t
    def advance(self, dt): self.t += dt

class AclService:
    def __init__(self):
        self.epoch = 0
        self.members = {}      # user -> set(groups)
        self.doc_acl = {}      # doc -> set(groups)
        self.listeners = []    # callbacks(doc_ids_changed or None, epoch)
    def add_user(self, user, groups): self.members[user] = set(groups)
    def write_doc(self, doc, acl): self.doc_acl[doc] = set(acl)
    def can_read_doc(self, user, doc): return bool(self.members.get(user, set()) & self.doc_acl[doc])
    def _bump(self, docs):
        self.epoch += 1
        for cb in self.listeners: cb(docs, self.epoch)
    def revoke_membership(self, user, group):
        self.members[user].discard(group)
        # affected set = docs whose ACL names `group` (label index lookup), not every artifact
        self._bump({d for d, a in self.doc_acl.items() if group in a})
    def set_doc_acl(self, doc, acl):
        self.doc_acl[doc] = set(acl)
        self._bump({doc})

class Refused(Exception): pass

class ArtifactStore:
    def __init__(self, acl, clock, lease_s=30.0, push=True):
        self.acl, self.clock, self.lease_s, self.push = acl, clock, lease_s, push
        self.art = {}         # id -> dict(inputs, version, tombstoned, content)
        self.lease = {}       # (user, id, version) -> (granted_epoch, expires_at)
        self.pending = []     # (docs, epoch) notifications not yet applied when push is delayed
        acl.listeners.append(self._on_acl_change)
    # ---- write / derive
    def derive(self, art_id, input_docs, content="summary"):
        prev = self.art.get(art_id)
        self.art[art_id] = dict(inputs=tuple(input_docs), version=(prev["version"] + 1 if prev else 1),
                                tombstoned=False, content=content, derived_epoch=self.acl.epoch)
    def audience(self, art_id, users):
        """label audience = intersection of input audiences (evaluated against CURRENT ACLs)."""
        a = self.art[art_id]
        return {u for u in users if all(self.acl.can_read_doc(u, d) for d in a["inputs"])}
    # ---- revocation path
    def _on_acl_change(self, docs, epoch):
        if self.push:
            self._apply(docs, epoch)
        else:
            self.pending.append((docs, epoch))
    def deliver_pending(self):
        for docs, epoch in self.pending: self._apply(docs, epoch)
        self.pending = []
    def _apply(self, docs, epoch):
        for a in self.art.values():
            if a["tombstoned"]: continue
            if set(a["inputs"]) & docs:
                # label index updated: artifact computed under the old label is tombstoned until re-derived
                a["tombstoned"] = True
        self.lease = {k: v for k, v in self.lease.items() if self.art[k[1]]["tombstoned"] is False}
    # ---- read path
    def read(self, user, art_id):
        a = self.art[art_id]
        if a["tombstoned"]:
            raise Refused("tombstoned")
        key = (user, art_id, a["version"])
        now = self.clock.now()
        l = self.lease.get(key)
        if l and now < l[1]:
            return a["content"]                         # decision cached under a still-valid lease
        # lease absent/expired: re-check entitlement against current ACLs & epoch
        if not all(self.acl.can_read_doc(user, d) for d in a["inputs"]):
            self.lease.pop(key, None)
            raise Refused("not entitled")
        self.lease[key] = (self.acl.epoch, now + self.lease_s)
        return a["content"]
