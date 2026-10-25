"""Storage backends. A backend only stores. It never decides who may read.

Documents are versioned and never rewritten. Artifacts are caches: any of them
may be deleted at any time and will simply be computed again.
"""

from __future__ import annotations

import threading
from abc import ABC, abstractmethod
from typing import NamedTuple, Sequence


class DocRow(NamedTuple):
    doc_id: str
    version: int
    sha: str
    deleted: bool


class CompositeRow(NamedTuple):
    prov: tuple[tuple[str, int], ...]  # sorted (doc_id, version) pairs
    payload: bytes


class Backend(ABC):
    # ---- documents
    @abstractmethod
    def load_docs(self) -> list[DocRow]:
        """The latest version row of every document ever stored."""

    @abstractmethod
    def add_doc_version(self, doc_id: str, version: int, text: str, sha: str) -> None: ...

    @abstractmethod
    def get_doc_text(self, doc_id: str, version: int) -> str | None: ...

    @abstractmethod
    def doc_versions(self, doc_id: str) -> list[int]: ...

    @abstractmethod
    def mark_deleted(self, doc_id: str) -> None:
        """Erase all text of the document. The version counter is kept."""

    # ---- artifact caches
    @abstractmethod
    def get_component(self, doc_id: str, version: int, kind: str, spec_version: str) -> bytes | None: ...

    @abstractmethod
    def put_component(self, doc_id: str, version: int, kind: str, spec_version: str, payload: bytes) -> None: ...

    @abstractmethod
    def get_composite(self, key: str) -> CompositeRow | None: ...

    @abstractmethod
    def put_composite(self, key: str, kind: str, prov: Sequence[tuple[str, int]], payload: bytes) -> None: ...

    @abstractmethod
    def purge_artifacts(self, doc_id: str, keep_version: int | None) -> None:
        """Delete components and composites that use ``doc_id`` at any version
        other than ``keep_version`` (or at any version if it is None)."""

    @abstractmethod
    def counts(self) -> dict[str, int]: ...

    def close(self) -> None:  # pragma: no cover - default is nothing to close
        pass


class MemoryBackend(Backend):
    """Everything in dicts. Thread safe. Lost when the process ends."""

    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._texts: dict[tuple[str, int], str | None] = {}
        self._sha: dict[tuple[str, int], str] = {}
        self._deleted: set[str] = set()
        self._comp: dict[tuple[str, int, str, str], bytes] = {}
        self._compos: dict[str, tuple[str, tuple[tuple[str, int], ...], bytes]] = {}

    def load_docs(self) -> list[DocRow]:
        with self._lock:
            latest: dict[str, int] = {}
            for d, v in self._texts:
                latest[d] = max(latest.get(d, 0), v)
            return [DocRow(d, v, self._sha[(d, v)], d in self._deleted) for d, v in sorted(latest.items())]

    def add_doc_version(self, doc_id, version, text, sha):
        with self._lock:
            self._texts[(doc_id, version)] = text
            self._sha[(doc_id, version)] = sha
            self._deleted.discard(doc_id)

    def get_doc_text(self, doc_id, version):
        with self._lock:
            return self._texts.get((doc_id, version))

    def doc_versions(self, doc_id):
        with self._lock:
            return sorted(v for d, v in self._texts if d == doc_id)

    def mark_deleted(self, doc_id):
        with self._lock:
            self._deleted.add(doc_id)
            for k in [k for k in self._texts if k[0] == doc_id]:
                self._texts[k] = None

    def get_component(self, doc_id, version, kind, spec_version):
        with self._lock:
            return self._comp.get((doc_id, version, kind, spec_version))

    def put_component(self, doc_id, version, kind, spec_version, payload):
        with self._lock:
            self._comp[(doc_id, version, kind, spec_version)] = payload

    def get_composite(self, key):
        with self._lock:
            row = self._compos.get(key)
            return CompositeRow(row[1], row[2]) if row else None

    def put_composite(self, key, kind, prov, payload):
        with self._lock:
            self._compos[key] = (kind, tuple(prov), payload)

    def purge_artifacts(self, doc_id, keep_version):
        with self._lock:
            for k in [k for k in self._comp if k[0] == doc_id and k[1] != keep_version]:
                del self._comp[k]
            for key in [
                key
                for key, (_, prov, _) in self._compos.items()
                if any(d == doc_id and v != keep_version for d, v in prov)
            ]:
                del self._compos[key]

    def counts(self):
        with self._lock:
            return {
                "doc_versions": len(self._texts),
                "components": len(self._comp),
                "composites": len(self._compos),
            }
