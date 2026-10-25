import re

import pytest

from labellattice import InMemoryAcl, LmfStore, ManualClock
from labellattice.backend import MemoryBackend

SRC = re.compile(r"([A-Za-z0-9_\-]+)@(\d+)")


def sources_in(payload: bytes) -> set[str]:
    """Every doc id mentioned as a source marker in a payload."""
    return {m.group(1) for m in SRC.finditer(payload.decode("ascii", "replace"))}


class CountingBackend(MemoryBackend):
    """Counts every call made to the backend (not the private helpers)."""

    def __init__(self):
        super().__init__()
        self.calls = 0

    def __getattribute__(self, name):
        attr = super().__getattribute__(name)
        if callable(attr) and not name.startswith("_") and name not in ("calls",):
            def wrapped(*a, **k):
                object.__setattr__(self, "calls", object.__getattribute__(self, "calls") + 1)
                return attr(*a, **k)
            return wrapped
        return attr


def build_world(lease_s=30.0, push=True, backend=None, compute=None, **kw):
    """alice and carol are in legal; bob is only in all; dave is in exec.

    memo is legal only, handbook is for everyone, board is exec only.
    """
    clock = ManualClock()
    acl = InMemoryAcl()
    acl.add_user("alice", {"all", "legal"})
    acl.add_user("bob", {"all"})
    acl.add_user("carol", {"all", "legal"})
    acl.add_user("dave", {"all", "exec"})
    acl.set_doc_acl("memo", {"legal"})
    acl.set_doc_acl("handbook", {"all"})
    acl.set_doc_acl("board", {"exec"})
    store = LmfStore(acl, backend=backend, compute=compute, clock=clock, lease_s=lease_s, push=push, **kw)
    store.put_document("memo", "The merger closes in March. Budget is 5 million.")
    store.put_document("handbook", "Work hours are nine to five. Budget is 5 million.")
    store.put_document("board", "The CEO will step down. Budget is 5 million.")
    return clock, acl, store


@pytest.fixture
def world():
    return build_world()
