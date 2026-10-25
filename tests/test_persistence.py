import sqlite3

import pytest

from labellattice import InMemoryAcl, LmfStore, Refused, SqliteBackend
from labellattice.errors import LabelLatticeError


def make_acl():
    acl = InMemoryAcl()
    acl.add_user("alice", {"all", "legal"}); acl.add_user("bob", {"all"})
    acl.set_doc_acl("memo", {"legal"}); acl.set_doc_acl("handbook", {"all"})
    return acl


def test_round_trip_keeps_documents_versions_and_cache(tmp_path):
    path = str(tmp_path / "s.db")
    acl = make_acl()
    with LmfStore(acl, backend=SqliteBackend(path)) as s1:
        s1.put_document("memo", "Merger in March."); s1.put_document("memo", "Merger in April.")
        s1.put_document("handbook", "Nine to five.")
        first = s1.query("alice", ["memo", "handbook"], "chunk_note")
    with LmfStore(acl, backend=SqliteBackend(path)) as s2:
        assert s2.documents() == {"memo": 2, "handbook": 1}
        again = s2.query("alice", ["memo", "handbook"], "chunk_note")
        assert again.payload == first.payload and again.source == "join-cache"
        assert s2.stats()["component_computes"] == 0
        assert s2.read_document("alice", "memo") == "Merger in April."
        assert s2.read_document("alice", "memo", version=1) == "Merger in March."


def test_the_gate_still_holds_after_a_restart(tmp_path):
    path = str(tmp_path / "s.db")
    acl = make_acl()
    with LmfStore(acl, backend=SqliteBackend(path)) as s1:
        s1.put_document("memo", "Secret."); s1.query("alice", ["memo"])
    with LmfStore(acl, backend=SqliteBackend(path)) as s2:
        with pytest.raises(Refused):
            s2.query("bob", ["memo"])


def test_leases_are_not_persisted(tmp_path):
    path = str(tmp_path / "s.db")
    acl = make_acl()
    with LmfStore(acl, backend=SqliteBackend(path), lease_s=3600) as s1:
        s1.put_document("memo", "Secret."); s1.query("alice", ["memo"])
    acl.revoke_membership("alice", "legal")
    with LmfStore(acl, backend=SqliteBackend(path), lease_s=3600) as s2:
        with pytest.raises(Refused):
            s2.query("alice", ["memo"])


def test_delete_and_version_counter_survive(tmp_path):
    path = str(tmp_path / "s.db")
    acl = make_acl()
    with LmfStore(acl, backend=SqliteBackend(path)) as s1:
        s1.put_document("memo", "One."); s1.put_document("handbook", "Two.")
        s1.query("alice", ["memo", "handbook"]); s1.delete_document("memo")
    with LmfStore(acl, backend=SqliteBackend(path)) as s2:
        assert s2.documents() == {"handbook": 1}
        with pytest.raises(Refused):
            s2.query("alice", ["memo", "handbook"])
        assert s2.stats()["stored_composites"] == 0
        assert s2.put_document("memo", "Three.") == 2


def test_deleted_text_is_really_erased_from_the_file(tmp_path):
    path = str(tmp_path / "s.db")
    acl = make_acl()
    with LmfStore(acl, backend=SqliteBackend(path)) as s:
        s.put_document("memo", "Zebra-unicorn-marker sentence."); s.query("alice", ["memo"])
        s.delete_document("memo")
    con = sqlite3.connect(path)
    dump = "\n".join(con.iterdump())
    con.close()
    assert "Zebra-unicorn-marker" not in dump


def test_memory_and_sqlite_give_identical_answers(tmp_path):
    outs = []
    for be in (None, SqliteBackend(str(tmp_path / "s.db"))):
        s = LmfStore(make_acl(), backend=be)
        s.put_document("memo", "Merger in March. Budget is big."); s.put_document("handbook", "Nine to five. Budget is big.")
        outs.append([s.query("alice", ["memo", "handbook"], k).payload for k in ("claims", "chunk_note", "kv_segment")])
    assert outs[0] == outs[1]


def test_composite_with_the_wrong_provenance_is_treated_as_a_miss(tmp_path):
    path = str(tmp_path / "s.db")
    acl = make_acl()
    with LmfStore(acl, backend=SqliteBackend(path)) as s1:
        s1.put_document("memo", "Merger in March."); s1.put_document("handbook", "Nine to five.")
        s1.query("alice", ["memo", "handbook"])
    con = sqlite3.connect(path)
    (prov,) = con.execute("SELECT prov FROM composites").fetchone()
    con.execute("UPDATE composites SET prov = ?", (prov.replace('"memo", 1', '"memo", 6'),))
    con.commit(); con.close()
    with LmfStore(acl, backend=SqliteBackend(path)) as s2:
        r = s2.query("alice", ["memo", "handbook"])
        assert r.source == "joined"            # the tampered row was not trusted
        assert b"memo@1" in r.payload


def test_unknown_schema_version_is_refused_loudly(tmp_path):
    path = str(tmp_path / "s.db")
    SqliteBackend(path).close()
    con = sqlite3.connect(path)
    con.execute("UPDATE meta SET v = '999' WHERE k = 'schema'")
    con.commit(); con.close()
    with pytest.raises(LabelLatticeError):
        SqliteBackend(path)


def test_wal_mode_and_clean_close(tmp_path):
    be = SqliteBackend(str(tmp_path / "s.db"))
    be.close()
    be.close()  # closing twice is harmless
