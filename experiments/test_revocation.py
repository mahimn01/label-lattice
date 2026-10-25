import json, unittest
from lattice import Clock, AclService, ArtifactStore, Refused

def mk(lease=30.0, push=True):
    clock = Clock(); acl = AclService()
    acl.add_user("alice", {"all", "legal"})
    acl.add_user("bob", {"all"})
    acl.add_user("carol", {"all", "legal"})
    acl.add_user("dave", {"all", "exec"})
    acl.write_doc("memo_restricted", {"legal"})
    acl.write_doc("handbook", {"all"})
    st = ArtifactStore(acl, clock, lease_s=lease, push=push)
    st.derive("summary", ["memo_restricted", "handbook"])
    return clock, acl, st

class RevocationTest(unittest.TestCase):
    def test_label_is_intersection_of_input_audiences(self):
        _, _, st = mk()
        users = ["alice", "bob", "carol", "dave"]
        self.assertEqual(st.audience("summary", users), {"alice", "carol"})   # not the union
        self.assertEqual(st.read("alice", "summary"), "summary")
        with self.assertRaises(Refused): st.read("bob", "summary")
        with self.assertRaises(Refused): st.read("dave", "summary")

    def test_revoked_user_refused_immediately_with_push_invalidation(self):
        clock, acl, st = mk()
        st.read("alice", "summary"); st.read("carol", "summary")   # lease granted
        e0 = acl.epoch
        acl.revoke_membership("alice", "legal")
        self.assertGreater(acl.epoch, e0)
        with self.assertRaises(Refused): st.read("alice", "summary")       # lag = 0
        with self.assertRaises(Refused): st.read("carol", "summary")       # artifact tombstoned until re-derived (conservative)
        st.derive("summary", ["memo_restricted", "handbook"])               # re-derive -> version 2, fresh label
        self.assertEqual(st.art["summary"]["version"], 2)
        self.assertEqual(st.read("carol", "summary"), "summary")            # still-entitled user served again
        with self.assertRaises(Refused): st.read("alice", "summary")        # revoked user stays refused

    def test_revocation_without_push_is_refused_within_lease_window(self):
        lease = 30.0
        clock, acl, st = mk(lease=lease, push=False)       # worst case: notifications delayed/lost
        st.read("alice", "summary")                         # t=0, lease valid until t=30
        clock.advance(10); t_revoke = clock.now()
        acl.revoke_membership("alice", "legal")
        # inside the lease window the cached decision may still be served (bounded staleness) ...
        clock.advance(5); st.read("alice", "summary")
        # ... but never past t_revoke + lease: refused by then, at the latest
        clock.t = t_revoke + lease
        with self.assertRaises(Refused): st.read("alice", "summary")
        # scan: first refusal time minus revoke time <= lease, for many revoke offsets
        for off in (0, 7, 29):
            c, a, s = mk(lease=lease, push=False)
            s.read("alice", "summary"); c.advance(off); tr = c.now()
            a.revoke_membership("alice", "legal")
            first = None
            while c.now() < tr + 3 * lease:
                try: s.read("alice", "summary")
                except Refused: first = c.now(); break
                c.advance(1)
            self.assertIsNotNone(first)
            self.assertLessEqual(first - tr, lease)
        # a user never entitled is refused immediately, lease or not
        with self.assertRaises(Refused): st.read("bob", "summary")

    def test_delayed_push_delivery_tombstones_when_applied(self):
        clock, acl, st = mk(lease=1000.0, push=False)
        st.read("alice", "summary"); acl.revoke_membership("alice", "legal")
        st.read("alice", "summary")                          # long lease: still served (documented risk of long leases)
        st.deliver_pending()
        with self.assertRaises(Refused): st.read("alice", "summary")

    def test_doc_acl_tightening_tombstones_dependants_only(self):
        _, acl, st = mk()
        st.derive("unrelated", ["handbook"])
        st.read("alice", "summary"); st.read("bob", "unrelated")
        acl.set_doc_acl("memo_restricted", {"exec"})
        with self.assertRaises(Refused): st.read("alice", "summary")
        self.assertEqual(st.read("bob", "unrelated"), "summary")   # affected set = exactly the dependants
        st.derive("summary", ["memo_restricted", "handbook"])
        self.assertEqual(st.read("dave", "summary"), "summary")    # new label audience = {exec} ∩ {all}
        with self.assertRaises(Refused): st.read("alice", "summary")

    def test_declassification_by_rederivation_not_redaction(self):
        _, acl, st = mk()
        st.derive("summary_public", ["handbook"])           # separate artifact with its own lineage
        self.assertEqual(st.read("bob", "summary_public"), "summary")
        self.assertNotIn("memo_restricted", st.art["summary_public"]["inputs"])
        with self.assertRaises(Refused): st.read("bob", "summary")   # restricted summary is never relabelled
        acl.revoke_membership("alice", "legal")
        self.assertEqual(st.read("bob", "summary_public"), "summary")  # unaffected by the revocation

    def test_epoch_monotonic(self):
        _, acl, st = mk()
        seen = [acl.epoch]
        acl.revoke_membership("alice", "legal"); seen.append(acl.epoch)
        acl.set_doc_acl("handbook", {"all", "exec"}); seen.append(acl.epoch)
        self.assertEqual(seen, sorted(set(seen)))

class SimConsistencyTest(unittest.TestCase):
    """Small-scale checks on the simulator itself: determinism and intersection semantics."""
    def _small(self):
        from sim import Params
        return Params(name="t", n_users=600, n_docs=6000, n_reads=40000, n_artifacts=2000, n_art_reads=10000)
    def test_deterministic(self):
        from sim import run
        a = run(self._small(), 3); b = run(self._small(), 3); c = run(self._small(), 4)
        a["seconds"] = b["seconds"] = c["seconds"] = 0
        self.assertEqual(json.dumps(a, sort_keys=True), json.dumps(b, sort_keys=True))
        self.assertNotEqual(json.dumps(a, sort_keys=True), json.dumps(c, sort_keys=True))
    def test_artifact_audience_is_set_intersection(self):
        import numpy as np
        from sim import build_org, build_docs, build_artifacts, pick
        P = self._small(); ss = np.random.SeedSequence(5); rs = [np.random.default_rng(s) for s in ss.spawn(4)]
        org = build_org(P, rs[0]); docs = build_docs(P, org, rs[1])
        doc_r = rs[2].integers(0, P.n_docs, 30000); user_r = rs[2].integers(0, P.n_users, 30000)
        cw = np.cumsum(np.ones(P.n_docs) / P.n_docs)
        art = build_artifacts(P, org, docs, cw, user_r, doc_r, rs[3])
        U, G = org["U"], org["G"]
        def aud_set(doc):
            row = docs["acl"][doc]; s = set()
            for e in row:
                if e < G: s |= set(org["pu"][org["pg"] == e].tolist())
                elif e < G + U: s.add(int(e - G))
            return s
        for a in range(0, 2000, 97):
            inter = set.intersection(*[aud_set(int(d)) for d in art["inputs"][a]])
            self.assertEqual(len(inter), int(art["size"][a]))
            self.assertEqual(int(docs["doc_size"][art["inputs"][a][0]]), len(aud_set(int(art["inputs"][a][0]))))

if __name__ == "__main__":
    unittest.main(verbosity=2)
