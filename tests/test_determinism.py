import hashlib
import os
import subprocess
import sys
from pathlib import Path

from tests.conftest import build_world

KINDS = ["claims", "chunk_note", "kv_segment"]
ROOT = Path(__file__).resolve().parent.parent


def digest(store, user="alice"):
    h = hashlib.sha256()
    for k in KINDS:
        for req in (["memo"], ["memo", "handbook"], ["handbook", "memo", "memo"]):
            h.update(store.query(user, req, k).payload)
    return h.hexdigest()


def test_two_fresh_stores_give_identical_bytes():
    assert digest(build_world()[2]) == digest(build_world()[2])


def test_order_and_duplicates_do_not_change_the_answer_or_the_cache_key():
    _, _, store = build_world()
    a = store.query("alice", ["memo", "handbook"], "kv_segment")
    b = store.query("alice", ["handbook", "memo", "handbook"], "kv_segment")
    assert a.payload == b.payload and b.source == "join-cache"


def test_eager_and_lazy_compute_agree():
    lazy = build_world()[2]
    eager = build_world(eager_kinds=("claims", "chunk_note", "kv_segment"))[2]
    assert digest(lazy) == digest(eager)


def test_user_identity_does_not_change_the_bytes():
    _, _, store = build_world()
    assert digest(store, "alice") == digest(store, "carol")


def test_hash_seed_independence():
    code = (
        "import sys; sys.path.insert(0, %r);"
        "from tests.test_determinism import digest; from tests.conftest import build_world;"
        "print(digest(build_world()[2]))" % str(ROOT)
    )
    outs = set()
    for seed in ("0", "1", "12345"):
        env = dict(os.environ, PYTHONHASHSEED=seed)
        r = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, env=env, check=True, cwd=ROOT)
        outs.add(r.stdout.strip())
    assert len(outs) == 1


def test_golden_digest_catches_accidental_format_changes():
    assert digest(build_world()[2]) == GOLDEN


GOLDEN = "7e4b073520ca82254e866dd05fdfc0af878716f9078a5dfc6a342c422e0666fd"
