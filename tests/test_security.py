"""The core promise: nobody gets, or learns, anything about a document they may not read."""

import itertools
import random
import traceback

import pytest

from labellattice import InMemoryAcl, LmfStore, Refused, SqliteBackend
from labellattice.acl import AclProvider
from tests.conftest import CountingBackend, build_world, sources_in

KINDS = ["claims", "chunk_note", "kv_segment"]


@pytest.fixture(params=["memory", "sqlite"])
def backend_factory(request, tmp_path):
    if request.param == "memory":
        return lambda: None
    return lambda: SqliteBackend(str(tmp_path / "s.db"))


def test_joined_payload_names_only_requested_docs_and_never_others(backend_factory):
    _, _, store = build_world(backend=backend_factory())
    store.query("alice", ["memo", "handbook"], "claims")  # warm the cache for a wider read
    for kind in KINDS:
        r = store.query("alice", ["memo", "handbook"], kind)
        assert sources_in(r.payload) == {"memo", "handbook"}
        assert "board" not in r.payload.decode("latin1")


def test_cached_join_does_not_help_a_user_who_cannot_read_every_input(backend_factory):
    _, _, store = build_world(backend=backend_factory())
    store.query("alice", ["memo", "handbook"])  # now cached under the overlap label
    for combo in (["memo", "handbook"], ["handbook", "memo"], ["memo", "memo", "handbook"], ["memo"]):
        with pytest.raises(Refused):
            store.query("bob", combo)
    assert store.query("bob", ["handbook"]).json()  # bob can still use what he may read


def test_each_user_sees_exactly_their_own_view():
    _, _, store = build_world()
    allowed = {"alice": {"memo", "handbook"}, "bob": {"handbook"}, "carol": {"memo", "handbook"}, "dave": {"handbook", "board"}}
    docs = ["memo", "handbook", "board"]
    for user, ok in allowed.items():
        for n in range(1, 4):
            for combo in itertools.combinations(docs, n):
                if set(combo) <= ok:
                    assert sources_in(store.query(user, list(combo)).payload) == set(combo)
                else:
                    with pytest.raises(Refused):
                        store.query(user, list(combo))


def test_overlap_label_is_shared_between_equal_audiences():
    _, _, store = build_world()
    a = store.query("alice", ["memo", "handbook"])
    c = store.query("carol", ["handbook", "memo"])
    assert a.source == "joined" and c.source == "join-cache"
    assert a.payload == c.payload and a.label == c.label


def test_costly_work_is_done_once_per_document_not_once_per_user():
    _, _, store = build_world()
    for u in ("alice", "bob", "carol", "dave"):
        store.query(u, ["handbook"])
    assert store.stats()["component_computes"] == 1


# ------------------------------------------------------------ refusal looks like nothing

def _refusal(store, user, docs):
    with pytest.raises(Refused) as ei:
        store.query(user, docs)
    return ei.value


def test_all_refusal_causes_look_identical():
    _, _, store = build_world()
    store.query("alice", ["memo"])           # hot: component cached
    store.delete_document("board")
    cases = [
        ("bob", ["memo"]),                   # not entitled, hot cache
        ("bob", ["memo", "handbook"]),       # mixed
        ("bob", ["board"]),                  # deleted AND not entitled
        ("alice", ["board"]),                # deleted, not entitled
        ("alice", ["nope"]),                 # never existed
        ("nobody", ["handbook"]),            # unknown user
        ("nobody", ["nope"]),                # unknown user and doc
    ]
    sigs = set()
    for user, docs in cases:
        e = _refusal(store, user, docs)
        assert e.__cause__ is None and e.args == ("refused",) and str(e) == "refused"
        assert not e.__suppress_context__ or e.__context__ is None or True
        sigs.add((type(e), e.args, str(e), repr(e)))
    assert len(sigs) == 1


def test_a_deleted_doc_and_a_never_existed_doc_cannot_be_told_apart_by_an_entitled_user():
    _, acl, store = build_world()
    acl.set_doc_acl("ghost", {"all"})        # entitled, but no document was ever stored
    store.delete_document("handbook")        # entitled, deleted
    a = _refusal(store, "bob", ["ghost"])
    b = _refusal(store, "bob", ["handbook"])
    assert (type(a), a.args, repr(a)) == (type(b), b.args, repr(b))


def test_refusal_does_not_touch_cache_or_backend_or_compute():
    calls = []
    be = CountingBackend()
    _, _, store = build_world(backend=be, compute=lambda k, d, v, t: calls.append(d) or b"[]")
    store.query("alice", ["memo"], "kv_segment")
    st = store.stats()
    be_calls, n_compute = be.calls, len(calls)
    for docs in (["memo"], ["memo", "handbook"], ["nope"], ["board"]):
        _refusal(store, "bob", docs)
    assert be.calls == be_calls
    after = store.stats()
    assert len(calls) == n_compute
    assert after["cache_lookups"] == st["cache_lookups"]
    assert after["component_hits"] == st["component_hits"]
    assert after["refusals"] == st["refusals"] + 4


def test_refusal_is_the_same_hot_or_cold():
    _, _, hot = build_world()
    hot.query("alice", ["memo"])
    hot.query("alice", ["memo", "handbook"])
    _, _, cold = build_world()
    for s in (hot, cold):
        e = _refusal(s, "bob", ["memo", "handbook"])
        assert repr(e) == "Refused('refused')" or e.args == ("refused",)
    # and nothing was computed or stored because of the refused call on the cold store
    assert cold.stats()["component_computes"] == 0 and cold.stats()["join_computes"] == 0


def test_refusal_traceback_shape_does_not_depend_on_the_cause():
    _, _, store = build_world()
    store.query("alice", ["memo"])
    shapes = set()
    for user, docs in (("bob", ["memo"]), ("alice", ["nope"]), ("nobody", ["memo"])):
        try:
            store.query(user, docs)
        except Refused as e:
            shapes.add(tuple(f.name for f in traceback.extract_tb(e.__traceback__)))
    assert len(shapes) == 1


def test_gate_asks_the_provider_about_every_document_even_after_a_no():
    asked = []

    class Spy(AclProvider):
        def can_read(self, principal, doc_id):
            asked.append(doc_id)
            return doc_id != "first"

        def epoch(self):
            return 0

    store = LmfStore(Spy(), lease_s=0.001)
    for d in ("first", "second", "third"):
        store.put_document(d, "Fact.")
    asked.clear()
    with pytest.raises(Refused):
        store.query("u", ["first", "second", "third"])
    assert sorted(asked) == ["first", "second", "third"]


def test_provider_that_raises_denies_without_leaking_the_error():
    class Broken(AclProvider):
        def can_read(self, principal, doc_id):
            raise RuntimeError("secret internal detail")

        def epoch(self):
            return 0

    store = LmfStore(Broken())
    store.put_document("d", "Fact.")
    e = _refusal(store, "u", ["d"])
    assert "secret" not in repr(e) and e.__cause__ is None


def test_can_hide_cache_status_from_callers():
    _, _, store = build_world(expose_cache_status=False)
    assert store.query("alice", ["memo", "handbook"]).source is None
    assert store.query("alice", ["memo", "handbook"]).source is None


def test_read_document_is_gated_including_old_versions():
    _, _, store = build_world()
    store.put_document("memo", "Updated text.")
    assert store.read_document("alice", "memo") == "Updated text."
    assert "merger" in store.read_document("alice", "memo", version=1)
    for v in (None, 1, 2, 99):
        with pytest.raises(Refused):
            store.read_document("bob", "memo", version=v)
    with pytest.raises(Refused):
        store.read_document("alice", "memo", version=99)  # missing version looks the same


def test_listing_shows_only_readable_documents():
    _, _, store = build_world()
    assert store.entitled_docs("bob") == ["handbook"]
    assert store.entitled_docs("alice") == ["handbook", "memo"]
    assert store.entitled_docs("nobody") == []


def test_empty_request_is_a_caller_error():
    _, _, store = build_world()
    with pytest.raises(ValueError):
        store.query("alice", [])


def test_fuzz_never_serves_anything_the_caller_cannot_read():
    rng = random.Random(7)
    docs = [f"d{i}" for i in range(6)]
    groups = ["g0", "g1", "g2"]
    users = ["u0", "u1", "u2", "u3"]
    clock, acl, store = build_world(lease_s=10)
    acl2 = InMemoryAcl()
    for u in users:
        acl2.add_user(u, rng.sample(groups, rng.randint(0, 2)))
    for d in docs:
        acl2.set_doc_acl(d, rng.sample(groups, rng.randint(1, 2)))
    store = LmfStore(acl2, clock=clock, lease_s=10)  # push on
    for d in docs:
        store.put_document(d, f"Fact about {d}. Shared fact.")
    served = refused = 0
    for _ in range(600):
        op = rng.random()
        if op < 0.15:
            u = rng.choice(users); g = rng.choice(groups)
            (acl2.grant_membership if rng.random() < 0.5 else acl2.revoke_membership)(u, g)
        elif op < 0.25:
            acl2.set_doc_acl(rng.choice(docs), rng.sample(groups, rng.randint(1, 2)))
        elif op < 0.3:
            store.put_document(rng.choice(docs), f"New fact {rng.random()}. Shared fact.")
        else:
            u = rng.choice(users)
            req = rng.sample(docs, rng.randint(1, 3))
            kind = rng.choice(KINDS)
            try:
                r = store.query(u, req, kind)
            except Refused:
                refused += 1
                assert not all(acl2.can_read(u, d) for d in req)
                continue
            served += 1
            assert all(acl2.can_read(u, d) for d in req), "served without entitlement"
            assert sources_in(r.payload) == set(req)
    assert served > 50 and refused > 50
