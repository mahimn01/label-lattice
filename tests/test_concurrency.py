import threading
import time

import pytest

from labellattice import InMemoryAcl, LmfStore, Refused, SqliteBackend
from tests.conftest import build_world, sources_in


def run_threads(n, fn):
    errors, barrier = [], threading.Barrier(n)

    def wrap(i):
        try:
            barrier.wait()
            fn(i)
        except BaseException as e:  # noqa: BLE001
            errors.append(e)

    ts = [threading.Thread(target=wrap, args=(i,)) for i in range(n)]
    [t.start() for t in ts]
    [t.join(30) for t in ts]
    assert not any(t.is_alive() for t in ts), "deadlock"
    return errors


def test_single_flight_for_components_and_joins():
    calls, lock = [], threading.Lock()

    def slow(kind, doc_id, version, text):
        time.sleep(0.05)
        with lock:
            calls.append(doc_id)
        return b"[]"

    _, _, store = build_world(compute=slow)
    users = ["alice", "carol"]
    errs = run_threads(16, lambda i: store.query(users[i % 2], ["memo", "handbook"], "kv_segment"))
    assert not errs
    assert sorted(calls) == ["handbook", "memo"]       # each document computed exactly once
    s = store.stats()
    assert s["component_computes"] == 2 and s["join_computes"] == 1
    assert s["join_hits"] == 15


def test_many_threads_same_results_as_serial():
    _, _, serial = build_world()
    want = serial.query("alice", ["memo", "handbook", "board"][:2], "chunk_note").payload
    _, _, store = build_world()
    got = []
    errs = run_threads(24, lambda i: got.append(store.query("alice", ["memo", "handbook"], "chunk_note").payload))
    assert not errs and set(got) == {want}


@pytest.mark.parametrize("sqlite", [False, True])
def test_stress_with_edits_never_leaks_or_crashes(tmp_path, sqlite):
    acl = InMemoryAcl()
    acl.add_user("legal", {"L", "A"}); acl.add_user("anyone", {"A"})
    for d in ("x", "y"):
        acl.set_doc_acl(d, {"A"})
    acl.set_doc_acl("secret", {"L"})
    be = SqliteBackend(str(tmp_path / "s.db")) if sqlite else None
    store = LmfStore(acl, backend=be, lease_s=0.05)
    for d in ("x", "y", "secret"):
        store.put_document(d, f"Fact {d}. Shared.")
    stop = threading.Event()
    problems = []

    def editor():
        i = 0
        while not stop.is_set():
            i += 1
            store.put_document(("x", "y", "secret")[i % 3], f"Fact {i}. Shared.")

    def reader(i):
        user = ("legal", "anyone")[i % 2]
        t_end = time.time() + 1.0
        while time.time() < t_end:
            for req in (["x", "y"], ["x", "secret"], ["secret"], ["y"]):
                try:
                    r = store.query(user, req, "claims")
                except Refused:
                    if user == "legal" or "secret" not in req:
                        problems.append(("wrongly refused", user, req))
                    continue
                if user == "anyone" and "secret" in sources_in(r.payload):
                    problems.append(("LEAK", req))
                if sources_in(r.payload) != set(req):
                    problems.append(("wrong sources", req))

    ed = threading.Thread(target=editor); ed.start()
    errs = run_threads(8, reader)
    stop.set(); ed.join()
    assert not errs, errs
    assert not problems, problems[:3]


def test_revoked_user_is_never_served_after_revoke_returns():
    _, acl, store = build_world(lease_s=3600)
    store.query("alice", ["memo", "handbook"])
    revoked = threading.Event()
    bad = []

    def work(i):
        if i == 0:
            time.sleep(0.05)
            acl.revoke_membership("alice", "legal")
            revoked.set()
            return
        for _ in range(3000):
            after = revoked.is_set()   # read BEFORE asking
            try:
                store.query("alice", ["memo", "handbook"])
            except Refused:
                continue
            if after:
                bad.append(1)

    errs = run_threads(8, work)
    assert not errs and not bad
    with pytest.raises(Refused):
        store.query("alice", ["memo"])


def test_concurrent_writers_on_sqlite_keep_every_version_unique(tmp_path):
    acl = InMemoryAcl(); acl.add_user("u", {"g"}); acl.set_doc_acl("d", {"g"})
    store = LmfStore(acl, backend=SqliteBackend(str(tmp_path / "s.db")))
    seen, lock = [], threading.Lock()

    def put(i):
        for j in range(10):
            v = store.put_document("d", f"text {i} {j}")
            with lock:
                seen.append(v)

    assert not run_threads(6, put)
    assert sorted(seen) == list(range(1, 61))
    assert store.documents()["d"] == 60


def test_acl_listeners_and_queries_do_not_deadlock():
    _, acl, store = build_world(lease_s=0.01)

    def work(i):
        for k in range(300):
            if i % 2:
                acl.revoke_membership("bob", "all") if k % 2 else acl.grant_membership("bob", "all")
            else:
                try:
                    store.query("bob", ["handbook"])
                except Refused:
                    pass
    assert not run_threads(8, work)
