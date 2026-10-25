"""Label-Lattice memoization with Lazy-Meet Factoring (LMF).

Share costly per-document AI work between users without sharing secrets.
"""

from .acl import AclChange, AclProvider, InMemoryAcl
from .artifacts import (
    KIND_CHUNK_NOTE,
    KIND_CLAIMS,
    KIND_KV_SEGMENT,
    ArtifactRegistry,
    ArtifactSpec,
    Part,
)
from .backend import Backend, MemoryBackend
from .clock import ManualClock, MonotonicClock
from .errors import LabelLatticeError, Refused
from .labels import Label
from .search import Answer, answer
from .sqlite_backend import SqliteBackend
from .store import LmfStore, Result

__version__ = "0.1.0"

__all__ = [
    "AclChange", "AclProvider", "InMemoryAcl",
    "KIND_CHUNK_NOTE", "KIND_CLAIMS", "KIND_KV_SEGMENT", "ArtifactRegistry", "ArtifactSpec", "Part",
    "Backend", "MemoryBackend", "SqliteBackend",
    "ManualClock", "MonotonicClock",
    "LabelLatticeError", "Refused", "Label",
    "Answer", "answer", "LmfStore", "Result",
]
