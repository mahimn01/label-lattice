"""Security + revocation tests for Lazy-Meet Factoring and the arm-B cover. Run: python3 test_lmf.py"""
import random, re, unittest
import numpy as np
from lattice import Clock, AclService, Refused
from lmf_store import LmfStore

MARK = re.compile(r"\[\[doc:([^@\]]+)@")

def mk(lease=30.0, push=True):
    clock = Clock(); acl = AclService()
    acl.add_user("alice", {"all", "legal"}); acl.add_user("bob", {"all"})
    acl.add_user("carol", {"all", "legal"}); acl.add_user("dave", {"all", "exec"})
    acl.write_doc("memo", {"legal"}); acl.write_doc("handbook", {"all"}); acl.write_doc("board", {"exec"})
    st = LmfStore(acl, clock, lease_s=lease, push=push)
    for d in ("memo", "handbook", "board"): st.put_doc(d)
    return clock, acl, st

def sources(content): return set(MARK.findall(content))

class SecurityTests(unittest.TestCase):
    def test_component_is_pure_function_of_one_doc(self):
        _, _, st = mk()
        c = st.read_component("alice", "memo")
        self.assertEqual(c["prov"], frozenset({"memo"})); self.assertEqual(sources(c["content"]), {"memo"})

    def test_composite_only_for_intersection_and_never_contains_unreadable_source(self):
        _, acl, st = mk()
        users = ["alice", "bob", "carol", "dave"]; inputs = ["memo", "handbook"]
        for u in users:
            readable = {d for d in inputs if acl.can_read_doc(u, d)}
            if readable == set(inputs):
                c = st.compose(u, "s", inputs); self.assertEqual(sources(c["content"]), set(inputs))
            else:
                with self.assertRaises(Refused): st.compose(u, "s", inputs)
        # bob can still get the broad component derived from the handbook, and ONLY that
        self.assertEqual(sources(st.read_component("bob", "handbook")["content"]), {"handbook"})
        with self.assertRaises(Refused): st.read_component("bob", "memo")

    def test_cached_composite_does_not_help_an_unentitled_principal(self):
        _, _, st = mk()
        st.compose("alice", "s", ["memo", "handbook"])          # now cached
        with self.assertRaises(Refused): st.compose("bob", "s", ["memo", "handbook"])
        with self.assertRaises(Refused): st.compose("bob", "s", ["handbook", "memo"])    # reordered inputs, same artifact
        with self.assertRaises(Refused): st.compose("dave", "s", ["handbook", "memo"])

    def test_refusal_touches_no_shared_cache_and_is_identical_hot_or_cold(self):
        _, _, st = mk()
        look0 = st.cache_lookups
        with self.assertRaises(Refused) as cold: st.read_component("bob", "memo")     # nothing cached
        st.read_component("alice", "memo")                                            # now cached
        look1 = st.cache_lookups
        with self.assertRaises(Refused) as hot: st.read_component("bob", "memo")
        self.assertEqual(str(cold.exception), str(hot.exception))      # same message hot or cold
        self.assertEqual(look0, 0); self.assertEqual(st.cache_lookups, look1)           # refused reads never reached the cache
        c0 = st.n_comp_compute
        with self.assertRaises(Refused): st.compose("bob", "x", ["memo", "handbook"])
        self.assertEqual(st.n_comp_compute, c0)                                        # a refused principal cannot trigger compute either

    def test_randomised_no_principal_ever_served_unreadable_source(self):
        """Random org, random reads interleaved with ACL changes/edits. push=True: every served read is entitled NOW."""
        rng = random.Random(7)
        for trial in range(40):
            clock = Clock(); acl = AclService()
            groups = [f"g{i}" for i in range(8)]; users = [f"u{i}" for i in range(25)]; docs = [f"d{i}" for i in range(20)]
            for u in users: acl.add_user(u, set(rng.sample(groups, rng.randint(1, 3))))
            for d in docs: acl.write_doc(d, set(rng.sample(groups, rng.randint(1, 3))))
            st = LmfStore(acl, clock, lease_s=20.0, push=True)
            for d in docs: st.put_doc(d)
            arts = {f"a{i}": rng.sample(docs, rng.randint(2, 5)) for i in range(15)}
            for step in range(300):
                op = rng.random()
                if op < 0.12:
                    u = rng.choice(users)
                    if acl.members[u]: acl.revoke_membership(u, rng.choice(sorted(acl.members[u])))
                elif op < 0.18: acl.set_doc_acl(rng.choice(docs), set(rng.sample(groups, rng.randint(1, 3))))
                elif op < 0.22: st.put_doc(rng.choice(docs), "edit")
                elif op < 0.3: clock.advance(rng.uniform(0, 15))
                else:
                    u = rng.choice(users); a = rng.choice(sorted(arts))
                    try: c = st.compose(u, a, arts[a])
                    except Refused:
                        continue
                    for d in sources(c["content"]):
                        self.assertTrue(acl.can_read_doc(u, d), (trial, step, u, a, d))
                    self.assertEqual(sources(c["content"]), set(arts[a]))

    def test_randomised_stale_service_bounded_by_lease_when_push_lost(self):
        rng = random.Random(11); lease = 20.0
        for trial in range(25):
            clock = Clock(); acl = AclService()
            groups = [f"g{i}" for i in range(6)]; users = [f"u{i}" for i in range(15)]; docs = [f"d{i}" for i in range(12)]
            for u in users: acl.add_user(u, set(rng.sample(groups, rng.randint(1, 3))))
            for d in docs: acl.write_doc(d, set(rng.sample(groups, rng.randint(1, 3))))
            st = LmfStore(acl, clock, lease_s=lease, push=False)       # push channel dead for the whole run
            for d in docs: st.put_doc(d)
            arts = {f"a{i}": rng.sample(docs, rng.randint(2, 4)) for i in range(10)}
            last_ok = {}                                               # (user, doc) -> last time observed entitled
            def snap():
                for u in users:
                    for d in docs:
                        if acl.can_read_doc(u, d): last_ok[(u, d)] = clock.now()
            snap()
            for step in range(300):
                op = rng.random()
                if op < 0.1:
                    u = rng.choice(users)
                    if acl.members[u]: acl.revoke_membership(u, rng.choice(sorted(acl.members[u])))
                    snap()
                elif op < 0.35: clock.advance(rng.uniform(0, 12)); snap()
                else:
                    u = rng.choice(users); a = rng.choice(sorted(arts))
                    try: c = st.compose(u, a, arts[a])
                    except Refused: continue
                    for d in c["prov"]:
                        self.assertGreaterEqual(last_ok[(u, d)], clock.now() - lease - 1e-9, (trial, step, u, d))

    def test_cover_arm_B_groups_inside_true_intersection(self):
        """Arm B: every chosen cover group is a subset of the naive set-intersection of the inputs' audiences,
        and every reader assigned to a group class is in that intersection."""
        from sim import Params, build_org, build_docs, build_artifacts, sample_readers
        from fix import arm_cover, _expand_components
        P = Params(name="t", n_users=600, n_docs=6000, n_reads=40000, n_artifacts=2000, n_art_reads=10000)
        rs = [np.random.default_rng(s) for s in np.random.SeedSequence(9).spawn(5)]
        org = build_org(P, rs[0]); docs = build_docs(P, org, rs[1])
        cw = np.cumsum(np.ones(P.n_docs) / P.n_docs)
        doc_r = rs[2].integers(0, P.n_docs, 30000); user_r = rs[2].integers(0, P.n_users, 30000)
        art = build_artifacts(P, org, docs, cw, user_r, doc_r, rs[3])
        NA = P.n_artifacts
        art_r = rs[4].integers(0, NA, 10000); art_r = art_r[art["size"][art_r] > 0]
        auser = sample_readers(art["aud"], art["bits"], art_r, org["act"], rs[4], P.n_users)
        s, valid, kd, items, users = _expand_components(art, art_r, auser)
        ra = np.bincount(art_r, minlength=NA)
        eff, uk, viol, M, chosen = arm_cover(org, docs, art, s, valid, kd, art_r, auser, ra)
        self.assertEqual(viol, 0)
        U, G = org["U"], org["G"]
        def aud_set(doc):
            st_ = set()
            for e in docs["acl"][doc]:
                if e < G: st_ |= set(org["pu"][org["pg"] == e].tolist())
                elif e < G + U: st_.add(int(e - G))
            return st_
        checked = 0; used_group = 0
        for a in range(0, NA, 23):
            inter = set.intersection(*[aud_set(int(d)) for d in art["inputs"][a]])
            for g in chosen[a]:
                if g < G:
                    self.assertTrue(set(org["pu"][org["pg"] == g].tolist()) <= inter); used_group += 1
            checked += 1
        for i in range(0, len(art_r), 17):          # every sampled reader is entitled to every input of the artifact it reads
            a = int(art_r[i]); u = int(auser[i])
            for d in art["inputs"][a]: self.assertIn(u, aud_set(int(d)))
        self.assertGreater(checked, 50)

    def test_simulated_readers_entitled_to_every_component(self):
        from sim import Params, build_org, build_docs, build_artifacts, sample_readers
        P = Params(name="t", n_users=600, n_docs=6000, n_reads=40000, n_artifacts=2000, n_art_reads=10000)
        rs = [np.random.default_rng(s) for s in np.random.SeedSequence(21).spawn(5)]
        org = build_org(P, rs[0]); docs = build_docs(P, org, rs[1])
        cw = np.cumsum(np.ones(P.n_docs) / P.n_docs)
        doc_r = rs[2].integers(0, P.n_docs, 30000); user_r = rs[2].integers(0, P.n_users, 30000)
        art = build_artifacts(P, org, docs, cw, user_r, doc_r, rs[3])
        art_r = rs[4].integers(0, P.n_artifacts, 5000); art_r = art_r[art["size"][art_r] > 0]
        auser = sample_readers(art["aud"], art["bits"], art_r, org["act"], rs[4], P.n_users)
        B = org["B"]; G, U = org["G"], org["U"]
        for a, u in zip(art_r[::7].tolist(), auser[::7].tolist()):
            for d in art["inputs"][a]:
                row = docs["acl"][int(d)]
                ok = any(e < G + U and ((B[e, u >> 3] >> (7 - (u & 7))) & 1) for e in row)
                self.assertTrue(ok)

class RevocationTests(unittest.TestCase):
    def test_push_revocation_immediate_and_nobody_else_recomputes(self):
        clock, acl, st = mk()
        st.compose("alice", "s", ["memo", "handbook"]); st.compose("carol", "s", ["memo", "handbook"])
        c0, j0 = st.n_comp_compute, st.n_join_compute
        acl.revoke_membership("alice", "legal")
        with self.assertRaises(Refused): st.compose("alice", "s", ["memo", "handbook"])    # lag 0
        self.assertIsNotNone(st.compose("carol", "s", ["memo", "handbook"]))              # still served
        self.assertEqual((st.n_comp_compute, st.n_join_compute), (c0, j0))                # revocation recomputed nothing
        with self.assertRaises(Refused): st.read_component("alice", "memo")               # component gate too
        self.assertIsNotNone(st.read_component("alice", "handbook"))                      # broad component still ok

    def test_lost_push_refusal_within_lease(self):
        lease = 30.0
        for off in (0, 7, 29):
            c, a, s = mk(lease=lease, push=False)
            s.compose("alice", "s", ["memo", "handbook"]); c.advance(off); tr = c.now()
            a.revoke_membership("alice", "legal")
            first = None
            while c.now() < tr + 3 * lease:
                try: s.compose("alice", "s", ["memo", "handbook"])
                except Refused: first = c.now(); break
                c.advance(1)
            self.assertIsNotNone(first); self.assertLessEqual(first - tr, lease)
        c, a, s = mk(lease=lease, push=False)
        with self.assertRaises(Refused): s.compose("bob", "s", ["memo", "handbook"])       # never entitled: refused at once

    def test_delayed_push_applied_on_delivery(self):
        clock, acl, st = mk(lease=1000.0, push=False)
        st.compose("alice", "s", ["memo", "handbook"]); acl.revoke_membership("alice", "legal")
        st.compose("alice", "s", ["memo", "handbook"])                # documented risk of long leases
        st.deliver_pending()
        with self.assertRaises(Refused): st.compose("alice", "s", ["memo", "handbook"])

    def test_membership_revoked_for_unrelated_doc_does_not_disturb_other_work(self):
        clock, acl, st = mk()
        st.compose("dave", "t", ["handbook", "board"]); st.compose("bob", "u", ["handbook"])
        c0, j0 = st.n_comp_compute, st.n_join_compute
        acl.revoke_membership("alice", "legal")
        st.compose("dave", "t", ["handbook", "board"]); st.compose("bob", "u", ["handbook"])
        self.assertEqual((st.n_comp_compute, st.n_join_compute), (c0, j0))

    def test_content_edit_tombstones_dependants_only(self):
        _, acl, st = mk()
        st.compose("alice", "s", ["memo", "handbook"]); st.compose("bob", "u", ["handbook"])
        c0 = st.n_comp_compute
        st.put_doc("memo", "edited")                                  # new version
        self.assertTrue(st.compos["s"]["tombstoned"]); self.assertFalse(st.compos["u"]["tombstoned"])
        c = st.compose("alice", "s", ["memo", "handbook"])
        self.assertEqual(st.n_comp_compute, c0 + 1)                   # only memo@2 recomputed; handbook component reused
        self.assertIn("memo@2", c["content"])

    def test_deletion_stops_service_everywhere(self):
        _, _, st = mk()
        st.compose("alice", "s", ["memo", "handbook"])
        st.delete_doc("memo")
        with self.assertRaises(Refused): st.read_component("alice", "memo")
        with self.assertRaises(Refused): st.compose("alice", "s", ["memo", "handbook"])
        self.assertIsNotNone(st.compose("bob", "u", ["handbook"]))

    def test_doc_acl_widening_then_tightening(self):
        _, acl, st = mk()
        with self.assertRaises(Refused): st.compose("bob", "s", ["memo", "handbook"])
        acl.set_doc_acl("memo", {"legal", "all"})                      # widened: bob may now read it
        self.assertIsNotNone(st.compose("bob", "s", ["memo", "handbook"]))
        acl.set_doc_acl("memo", {"legal"})                             # tightened again, push on
        with self.assertRaises(Refused): st.compose("bob", "s", ["memo", "handbook"])
        self.assertIsNotNone(st.compose("alice", "s", ["memo", "handbook"]))

if __name__ == "__main__":
    unittest.main(verbosity=2)
