import json

import pytest

from labellattice import ArtifactRegistry, ArtifactSpec, LmfStore, InMemoryAcl
from labellattice.artifacts import default_compute, KIND_CLAIMS, KIND_CHUNK_NOTE, KIND_KV_SEGMENT, Part
from tests.conftest import build_world


def test_three_default_kinds():
    assert ArtifactRegistry.default().kinds() == sorted([KIND_CLAIMS, KIND_CHUNK_NOTE, KIND_KV_SEGMENT])


def test_claims_split_and_dedupe():
    out = json.loads(default_compute(KIND_CLAIMS, "d", 1, "A is true. B is true.\nA is true."))
    assert [c["text"] for c in out] == ["A is true.", "B is true."]
    assert out[0]["srcs"] == ["d@1"]


def test_claims_join_is_an_exact_union():
    _, _, store = build_world()
    r = store.query("alice", ["memo", "handbook"], "claims")
    texts = {c["text"]: c["srcs"] for c in r.json()}
    assert texts["Budget is 5 million."] == ["handbook@1", "memo@1"]
    assert set(texts) == {
        "The merger closes in March.", "Budget is 5 million.", "Work hours are nine to five."}


def test_every_kind_can_be_queried_and_joined():
    _, _, store = build_world()
    for kind in (KIND_CLAIMS, KIND_CHUNK_NOTE, KIND_KV_SEGMENT):
        one = store.query("alice", ["memo"], kind)
        two = store.query("alice", ["memo", "handbook"], kind)
        assert one.payload and two.payload and one.payload != two.payload


def test_unknown_kind_is_an_error_not_a_refusal():
    _, _, store = build_world()
    with pytest.raises(ValueError):
        store.query("alice", ["memo"], "no-such-kind")


def test_custom_compute_callback_sees_one_document_only():
    seen = []

    def compute(kind, doc_id, version, text):
        seen.append((kind, doc_id, version, text))
        return f"{kind}:{doc_id}@{version}:{len(text)}".encode()

    _, _, store = build_world(compute=compute)
    store.query("alice", ["memo", "handbook"], "kv_segment")
    assert {s[1] for s in seen} == {"memo", "handbook"}
    assert all(len(s) == 4 for s in seen)
    # each call got exactly its own document's text
    texts = {s[1]: s[3] for s in seen}
    assert "merger" in texts["memo"] and "merger" not in texts["handbook"]


def test_custom_spec_with_its_own_join():
    reg = ArtifactRegistry([ArtifactSpec(
        "wc", lambda k, d, v, t: str(len(t.split())).encode(),
        lambda k, parts: str(sum(int(p.payload) for p in parts)).encode())])
    acl = InMemoryAcl(); acl.add_user("u", {"g"}); acl.set_doc_acl("a", {"g"}); acl.set_doc_acl("b", {"g"})
    store = LmfStore(acl, registry=reg)
    store.put_document("a", "one two three"); store.put_document("b", "four five")
    assert store.query("u", ["a", "b"], "wc").payload == b"5"


def test_compute_failure_is_not_cached():
    calls = {"n": 0}

    def flaky(kind, doc_id, version, text):
        calls["n"] += 1
        if calls["n"] == 1:
            raise RuntimeError("boom")
        return b"ok"

    _, _, store = build_world(compute=flaky)
    with pytest.raises(RuntimeError):
        store.query("alice", ["memo"], "claims")
    assert store.query("alice", ["memo"], "claims").payload == b"ok"


def test_payloads_must_be_bytes():
    _, _, store = build_world(compute=lambda k, d, v, t: 123)
    with pytest.raises(TypeError):
        store.query("alice", ["memo"], "claims")


def test_changing_spec_version_misses_the_old_cache():
    from labellattice.backend import MemoryBackend
    be = MemoryBackend()
    _, acl, s1 = build_world(backend=be)
    s1.query("alice", ["memo"], "claims")
    reg = ArtifactRegistry([ArtifactSpec(KIND_CLAIMS, default_compute, lambda k, p: b"x", version="2")])
    s2 = LmfStore(acl, backend=be, registry=reg)
    before = s2.stats()["component_computes"]
    s2.query("alice", ["memo"], "claims")
    assert s2.stats()["component_computes"] == before + 1
