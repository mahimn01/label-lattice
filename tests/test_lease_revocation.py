"""Revocation: a push cuts access at once, and a lease bounds staleness if the push is lost."""

import random

import pytest

from labellattice import InMemoryAcl, LmfStore, ManualClock, Refused
from labellattice.acl import AclProvider
from tests.conftest import build_world


def test_push_revocation_is_immediate():
    _, acl, store = build_world(lease_s=3600)
    assert store.query("alice", ["memo", "handbook"]).json()
    acl.revoke_membership("alice", "legal")
    with pytest.raises(Refused):
        store.query("alice", ["memo", "handbook"])
    with pytest.raises(Refused):
        store.query("alice", ["memo"])
    with pytest.raises(Refused):
        store.read_document("alice", "memo")
    assert store.query("alice", ["handbook"]).json()  # still entitled to the rest


def test_revoking_one_user_does_not_hurt_or_recompute_for_others():
    _, acl, store = build_world(lease_s=3600)
    store.query("alice", ["memo", "handbook"]); store.query("carol", ["memo", "handbook"])
    before = store.stats()
    acl.revoke_membership("alice", "legal")
    r = store.query("carol", ["memo", "handbook"])
    after = store.stats()
    assert r.source == "join-cache"
    assert after["component_computes"] == before["component_computes"]
    assert after["join_computes"] == before["join_computes"]


def test_doc_acl_change_is_immediate_for_that_doc_only():
    _, acl, store = build_world(lease_s=3600)
    store.query("carol", ["memo"]); store.query("carol", ["handbook"])
    acl.set_doc_acl("memo", {"exec"})
    with pytest.raises(Refused):
        store.query("carol", ["memo"])
    assert store.query("carol", ["handbook"]).json()
    assert store.query("dave", ["memo"]).json()  # newly entitled at once: denials are never cached


def test_removed_user_is_cut_off():
    _, acl, store = build_world(lease_s=3600)
    store.query("bob", ["handbook"])
    acl.remove_user("bob")
    with pytest.raises(Refused):
        store.query("bob", ["handbook"])


def test_lease_bounds_staleness_when_the_push_is_lost():
    clock, acl, store = build_world(lease_s=30, push=False)
    store.query("alice", ["memo"])
    acl.revoke_membership("alice", "legal")
    clock.advance(29.9)
    assert store.query("alice", ["memo"]).json()      # inside the bound: may still be served
    clock.advance(0.2)
    with pytest.raises(Refused):                      # past the bound: must be refused
        store.query("alice", ["memo"])


def test_epoch_fast_path_renews_without_asking_the_provider_per_document():
    class Spy(InMemoryAcl):
        reads = 0

        def can_read(self, principal, doc_id):
            Spy.reads += 1
            return super().can_read(principal, doc_id)

    acl = Spy(); acl.add_user("u", {"g"}); acl.set_doc_acl("d", {"g"})
    clock = ManualClock()
    store = LmfStore(acl, clock=clock, lease_s=10)
    store.put_document("d", "Fact.")
    store.query("u", ["d"])
    assert Spy.reads == 1
    clock.advance(11)
    store.query("u", ["d"])                           # lease ended, epoch unchanged
    assert Spy.reads == 1 and store.stats()["lease_renewals"] == 1
    acl.set_doc_acl("other", {"g"})                   # any change moves the epoch
    clock.advance(11)
    store.query("u", ["d"])
    assert Spy.reads == 2


def test_epoch_fast_path_never_keeps_a_revoked_user_when_the_push_is_lost():
    clock, acl, store = build_world(lease_s=10, push=False)
    store.query("alice", ["memo"])
    acl.revoke_membership("alice", "legal")
    clock.advance(11)
    with pytest.raises(Refused):
        store.query("alice", ["memo"])


def test_a_push_during_a_provider_check_does_not_leave_a_lease_behind():
    class Racy(AclProvider):
        def __init__(self):
            self.allowed = True
            self.listeners = []
            self.on_check = None
            self.n = 0

        def can_read(self, principal, doc_id):
            result = self.allowed
            if self.on_check:
                self.on_check()   # the revocation lands while this check is in flight
            return result

        def epoch(self):
            return self.n

        def subscribe(self, listener):
            self.listeners.append(listener)
            return lambda: None

    from labellattice import AclChange
    acl = Racy()
    store = LmfStore(acl, lease_s=3600)
    store.put_document("d", "Fact.")

    def revoke():
        acl.allowed = False; acl.n += 1
        for l in acl.listeners:
            l(AclChange(docs=frozenset({"d"}), principals=frozenset({"u"}), epoch=acl.n))
    acl.on_check = revoke
    store.query("u", ["d"])      # this one began before the revocation, so it may succeed
    acl.on_check = None
    with pytest.raises(Refused):  # but it must not have installed a lease
        store.query("u", ["d"])


def test_sweep_removes_expired_leases_only():
    clock, _, store = build_world(lease_s=10)
    store.query("alice", ["memo"])
    clock.advance(5)
    store.query("bob", ["handbook"])
    clock.advance(6)
    assert store.stats()["active_leases"] >= 2
    store.sweep()
    s = store.stats()["active_leases"]
    assert s == 1  # only bob's, granted five seconds later


@pytest.mark.parametrize("push", [True, False])
def test_randomized_bound(push):
    """Whenever a read is served, the user was entitled at some moment within the last lease_s."""
    rng = random.Random(3 if push else 4)
    lease = 20.0
    clock = ManualClock()
    acl = InMemoryAcl()
    users = ["u0", "u1", "u2"]; docs = ["a", "b", "c"]
    for u in users:
        acl.add_user(u, {"g"})
    for d in docs:
        acl.set_doc_acl(d, {"g"})
    store = LmfStore(acl, clock=clock, lease_s=lease, push=push)
    for d in docs:
        store.put_document(d, f"Fact {d}.")
    last_entitled: dict[tuple[str, str], float] = {(u, d): 0.0 for u in users for d in docs}
    served = 0
    for _ in range(1500):
        now = clock.now()
        for u in users:
            for d in docs:
                if acl.can_read(u, d):
                    last_entitled[(u, d)] = now
        x = rng.random()
        if x < 0.1:
            u = rng.choice(users)
            (acl.revoke_membership if rng.random() < 0.6 else acl.grant_membership)(u, "g")
        elif x < 0.15:
            acl.set_doc_acl(rng.choice(docs), {"g"} if rng.random() < 0.5 else {"x"})
        elif x < 0.4:
            clock.advance(rng.uniform(0, 12))
        else:
            u = rng.choice(users); req = rng.sample(docs, rng.randint(1, 3))
            try:
                store.query(u, req)
            except Refused:
                if push:  # with push, a no must be a real no
                    assert not all(acl.can_read(u, d) for d in req)
                continue
            served += 1
            for d in req:
                if push:
                    assert acl.can_read(u, d), "push must cut access at once"
                assert clock.now() - last_entitled[(u, d)] <= lease + 1e-9
    assert served > 30


def test_deleted_document_is_gone_for_everyone_and_its_joins_are_purged():
    _, _, store = build_world(lease_s=3600)
    store.query("alice", ["memo", "handbook"])
    assert store.delete_document("memo") is True
    with pytest.raises(Refused):
        store.query("alice", ["memo", "handbook"])
    with pytest.raises(Refused):
        store.read_document("alice", "memo")
    s = store.stats()
    assert s["stored_composites"] == 0
    assert store.delete_document("memo") is False


def test_new_version_replaces_old_everywhere():
    _, _, store = build_world()
    store.query("alice", ["memo", "handbook"])
    v = store.put_document("memo", "The merger is cancelled.")
    assert v == 2
    r = store.query("alice", ["memo", "handbook"])
    assert dict(r.versions)["memo"] == 2 and r.source == "joined"
    assert b"memo@1" not in r.payload and b"merger is cancelled" in r.payload
    assert store.put_document("memo", "The merger is cancelled.") == 2  # same text: no new version


def test_versions_are_never_reused_after_delete():
    _, _, store = build_world()
    store.delete_document("memo")
    assert store.put_document("memo", "Fresh text.") == 2  # v1 was never handed out again
