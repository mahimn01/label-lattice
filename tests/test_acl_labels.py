import pytest

from labellattice import InMemoryAcl, Label, Refused
from labellattice.acl import AclProvider


def test_can_read_by_group_and_unknown_is_false():
    acl = InMemoryAcl()
    acl.add_user("a", {"g"})
    acl.set_doc_acl("d", {"g"})
    assert acl.can_read("a", "d")
    assert not acl.can_read("nobody", "d")
    assert not acl.can_read("a", "no-such-doc")


def test_epoch_goes_up_on_every_change():
    acl = InMemoryAcl()
    seen = [acl.epoch()]
    acl.add_user("a", {"g"}); seen.append(acl.epoch())
    acl.set_doc_acl("d", {"g"}); seen.append(acl.epoch())
    acl.revoke_membership("a", "g"); seen.append(acl.epoch())
    acl.grant_membership("a", "g"); seen.append(acl.epoch())
    acl.remove_doc_acl("d"); seen.append(acl.epoch())
    acl.remove_user("a"); seen.append(acl.epoch())
    assert seen == sorted(set(seen)) and len(seen) == 7


def test_push_notice_names_what_changed():
    acl = InMemoryAcl()
    acl.add_user("a", {"g", "h"})
    acl.set_doc_acl("d1", {"g"})
    acl.set_doc_acl("d2", {"h"})
    got = []
    unsub = acl.subscribe(got.append)
    acl.revoke_membership("a", "g")
    assert got[-1].docs == frozenset({"d1"}) and got[-1].principals == frozenset({"a"})
    acl.set_doc_acl("d2", {"x"})
    assert got[-1].docs == frozenset({"d2"}) and got[-1].principals is None
    unsub()
    n = len(got)
    acl.set_doc_acl("d2", {"y"})
    assert len(got) == n


def test_listener_may_call_back_into_the_provider():
    acl = InMemoryAcl()
    acl.subscribe(lambda change: acl.epoch())
    acl.add_user("a", {"g"})


def test_snapshot_round_trip():
    acl = InMemoryAcl()
    acl.add_user("a", {"g"}); acl.set_doc_acl("d", {"g"})
    again = InMemoryAcl.from_dict(acl.to_dict())
    assert again.can_read("a", "d") and again.epoch() == acl.epoch()


def test_label_is_the_overlap_of_audiences():
    acl = InMemoryAcl()
    acl.add_user("alice", {"all", "legal"}); acl.add_user("bob", {"all"}); acl.add_user("dave", {"exec"})
    acl.set_doc_acl("memo", {"legal"}); acl.set_doc_acl("handbook", {"all"})
    users = ["alice", "bob", "dave"]
    assert Label.of(["memo"]).audience(acl, users) == {"alice"}
    assert Label.of(["handbook"]).audience(acl, users) == {"alice", "bob"}
    both = Label.of(["memo", "handbook"])
    assert both.audience(acl, users) == {"alice"}  # the overlap, never the union
    assert Label.of(["memo"]).meet(Label.of(["handbook"])) == both


def test_label_needs_a_document():
    with pytest.raises(ValueError):
        Label.of([])


def test_acl_provider_is_pluggable():
    class AllowList(AclProvider):
        def can_read(self, principal, doc_id):
            return (principal, doc_id) in {("x", "d")}

        def epoch(self):
            return 0

    from labellattice import LmfStore
    store = LmfStore(AllowList())
    store.put_document("d", "One fact.")
    assert store.query("x", ["d"]).json()[0]["text"] == "One fact."
    with pytest.raises(Refused):
        store.query("y", ["d"])
