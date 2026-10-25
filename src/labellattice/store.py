"""The LMF store: Lazy-Meet Factoring, end to end.

Rules this file enforces:

1. Costly work is done once per (document, version, kind). Its label is that
   one document. It is shared by everyone who may read that document.
2. A joined result over several documents is cheap. It is built on request and
   cached under the overlap label (all the documents it came from).
3. The entitlement gate runs FIRST on every read. It asks the ACL provider (or
   a valid lease). Only after the gate passes does the store touch any shared
   cache or backend. A refused caller causes no cache lookup, no compute and no
   backend call, and gets the same error whatever the reason.
4. Entitlement decisions are cached as leases. A lease ends when it expires,
   or sooner when the ACL provider pushes a change. So stale access can never
   outlast one lease, even if the push is lost.
5. A new document version or a delete removes the old artifacts and every join
   that used them.
"""

from __future__ import annotations

import hashlib
import threading
from dataclasses import dataclass
from typing import Iterable, Sequence

from .acl import AclChange, AclProvider
from .artifacts import (
    ArtifactRegistry,
    ArtifactSpec,
    ComputeFn,
    Part,
    canonical_json,
)
from .backend import Backend, MemoryBackend
from .clock import Clock, MonotonicClock
from .errors import Refused
from .labels import Label

SOURCE_COMPONENT_HIT = "component-cache"
SOURCE_COMPUTED = "computed"
SOURCE_JOIN_HIT = "join-cache"
SOURCE_JOINED = "joined"

_STRIPES = 64


@dataclass(frozen=True)
class Result:
    """What an entitled caller gets back."""

    payload: bytes
    kind: str
    label: Label
    versions: tuple[tuple[str, int], ...]
    # Where the result came from. None if the store hides cache status.
    source: str | None

    def json(self):
        import json

        return json.loads(self.payload)


@dataclass
class _Meta:
    version: int
    deleted: bool
    sha: str


@dataclass
class _Lease:
    expires: float
    epoch: int


def _sha(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def composite_key(kind: str, spec_version: str, pairs: Sequence[tuple[str, int]]) -> str:
    return hashlib.sha256(canonical_json([kind, spec_version, [[d, v] for d, v in pairs]])).hexdigest()


class LmfStore:
    def __init__(
        self,
        acl: AclProvider,
        backend: Backend | None = None,
        registry: ArtifactRegistry | None = None,
        compute: ComputeFn | None = None,
        clock: Clock | None = None,
        lease_s: float = 30.0,
        push: bool = True,
        eager_kinds: Iterable[str] | None = None,
        expose_cache_status: bool = True,
    ) -> None:
        if lease_s <= 0:
            raise ValueError("lease_s must be positive")
        self.acl = acl
        self.backend = backend if backend is not None else MemoryBackend()
        reg = registry if registry is not None else ArtifactRegistry.default()
        self.registry = reg.with_compute(compute) if compute is not None else reg
        self.clock = clock if clock is not None else MonotonicClock()
        self.lease_s = float(lease_s)
        self.push = push
        self.expose_cache_status = expose_cache_status
        self.eager_kinds = tuple(() if eager_kinds is None else eager_kinds)
        for k in self.eager_kinds:
            self.registry.get(k)

        self._mu = threading.RLock()
        # Two separate lock arrays (never one inside the other's own array), so no deadlock.
        self._stripes = [threading.Lock() for _ in range(_STRIPES)]       # per component key
        self._join_stripes = [threading.Lock() for _ in range(_STRIPES)]  # per composite key
        self._meta: dict[str, _Meta] = {r.doc_id: _Meta(r.version, r.deleted, r.sha) for r in self.backend.load_docs()}
        self._leases: dict[str, dict[str, _Lease]] = {}  # doc -> principal -> lease
        self._drop_gen = 0
        self._served: set[tuple[str, str, int, str]] = set()  # what a per-user cache would hold
        self._stats = dict(
            requests=0, refusals=0, cache_lookups=0,
            component_hits=0, component_computes=0, join_hits=0, join_computes=0,
            lease_hits=0, lease_renewals=0, provider_checks=0, lease_grants=0, leases_dropped=0, provider_errors=0,
        )
        self._unsubscribe = self.acl.subscribe(self._on_acl_change) if push else (lambda: None)

    # ------------------------------------------------------------ lifecycle
    def close(self) -> None:
        self._unsubscribe()
        self.backend.close()

    def __enter__(self) -> "LmfStore":
        return self

    def __exit__(self, *exc) -> None:
        self.close()

    # ------------------------------------------------------------ documents (ingest side, trusted)
    def put_document(self, doc_id: str, text: str, precompute: bool = True) -> int:
        """Store a new version of a document and return its version number.

        Putting the same text again does nothing and returns the current
        version. With ``precompute`` the kinds named in ``eager_kinds`` are
        computed now, under that document's own label. Other kinds are computed
        on first use.
        """
        if not isinstance(doc_id, str) or not doc_id:
            raise ValueError("doc_id must be a non-empty string")
        if not isinstance(text, str):
            raise TypeError("text must be a string")
        sha = _sha(text)
        with self._mu:
            m = self._meta.get(doc_id)
            if m is not None and not m.deleted and m.sha == sha:
                return m.version
            version = (m.version if m else 0) + 1
            self.backend.add_doc_version(doc_id, version, text, sha)
            self._meta[doc_id] = _Meta(version, False, sha)
            if m is not None:
                self.backend.purge_artifacts(doc_id, keep_version=version)
        if precompute:
            for kind in self.eager_kinds:
                self._component(doc_id, version, self.registry.get(kind))
        return version

    def delete_document(self, doc_id: str) -> bool:
        """Erase the document's text, all its artifacts and every join that used it."""
        with self._mu:
            m = self._meta.get(doc_id)
            if m is None or m.deleted:
                return False
            m.deleted = True
            self.backend.mark_deleted(doc_id)
            self.backend.purge_artifacts(doc_id, keep_version=None)
            self._drop_leases(frozenset({doc_id}), None)
            return True

    def documents(self) -> dict[str, int]:
        """Admin view: live document ids and their current versions."""
        with self._mu:
            return {d: m.version for d, m in sorted(self._meta.items()) if not m.deleted}

    # ------------------------------------------------------------ the gate
    def _on_acl_change(self, change: AclChange) -> None:
        self._drop_leases(change.docs, change.principals)

    def _drop_leases(self, docs: frozenset[str] | None, principals: frozenset[str] | None) -> None:
        with self._mu:
            self._drop_gen += 1
            targets = list(self._leases) if docs is None else [d for d in docs if d in self._leases]
            for d in targets:
                per = self._leases[d]
                if principals is None:
                    self._stats["leases_dropped"] += len(per)
                    per.clear()
                else:
                    for p in principals:
                        if per.pop(p, None) is not None:
                            self._stats["leases_dropped"] += 1
                if not per:
                    del self._leases[d]

    def _entitled(self, principal: str, doc_id: str) -> bool:
        now = self.clock.now()
        with self._mu:
            lease = self._leases.get(doc_id, {}).get(principal)
            if lease is not None and now < lease.expires:
                self._stats["lease_hits"] += 1
                return True
            gen = self._drop_gen
            if lease is not None:
                del self._leases[doc_id][principal]
        # Read the epoch BEFORE asking, so a change in between is never missed.
        failed = False
        try:
            epoch = self.acl.epoch()
            if lease is not None and lease.epoch == epoch:
                allowed, renewed = True, True  # nothing changed anywhere since the lease was granted
            else:
                allowed, renewed = bool(self.acl.can_read(principal, doc_id)), False
        except Exception:  # fail closed, and say nothing about why
            epoch, allowed, renewed, failed = -1, False, False, True
        with self._mu:
            if failed:
                self._stats["provider_errors"] += 1
            self._stats["lease_renewals" if renewed else "provider_checks"] += 1
            # If a change was pushed while we were asking, do not keep the lease.
            if allowed and gen == self._drop_gen:
                self._leases.setdefault(doc_id, {})[principal] = _Lease(now + self.lease_s, epoch)
                self._stats["lease_grants"] += 1
        return allowed

    def _gate(self, principal: str, doc_ids: Sequence[str]) -> dict[str, int]:
        """Entitlement gate. Raises the one ``Refused`` error for every failure.

        Does the same work for every document even after a failure, and checks
        that documents exist only after entitlement, so nothing but the final
        yes or no depends on the answer.
        """
        with self._mu:
            self._stats["requests"] += 1
        verdicts = [self._entitled(principal, d) for d in doc_ids]  # no early exit
        with self._mu:
            metas = [self._meta.get(d) for d in doc_ids]
            ok = all(verdicts) and all(m is not None and not m.deleted for m in metas)
            if not ok:
                self._stats["refusals"] += 1
                raise Refused()
            return {d: m.version for d, m in zip(doc_ids, metas)}  # type: ignore[union-attr]

    def entitled_docs(self, principal: str) -> list[str]:
        """The live documents this principal may read. Never raises."""
        with self._mu:
            live = [d for d, m in sorted(self._meta.items()) if not m.deleted]
        return [d for d in live if self._entitled(principal, d)]

    # ------------------------------------------------------------ reads
    def read_document(self, principal: str, doc_id: str, version: int | None = None) -> str:
        """The text of a document, behind the same gate."""
        vers = self._gate(principal, [doc_id])
        v = vers[doc_id] if version is None else version
        text = self.backend.get_doc_text(doc_id, v)
        if text is None:
            raise Refused()
        return text

    def query(self, principal: str, doc_ids: Iterable[str], kind: str = "claims") -> Result:
        """The artifact of ``kind`` over ``doc_ids``, joined if there are several.

        Raises ``Refused`` unless ``principal`` may read every one of them.
        """
        spec = self.registry.get(kind)  # public information, safe to fail loudly
        ids = sorted(set(doc_ids))
        if not ids:
            raise ValueError("query needs at least one document")
        versions = self._gate(principal, ids)  # <- nothing below runs for a refused caller
        pairs = tuple((d, versions[d]) for d in ids)
        with self._mu:
            for d, v in pairs:
                self._served.add((principal, d, v, kind))
        label = Label.of(ids)

        if len(ids) == 1:
            payload, computed = self._component(ids[0], pairs[0][1], spec)
            src = SOURCE_COMPUTED if computed else SOURCE_COMPONENT_HIT
            return self._result(payload, kind, label, pairs, src)

        key = composite_key(kind, spec.version, pairs)
        with self._mu:
            self._stats["cache_lookups"] += 1
        row = self.backend.get_composite(key)
        if row is not None and tuple(row.prov) == pairs:
            with self._mu:
                self._stats["join_hits"] += 1
            return self._result(row.payload, kind, label, pairs, SOURCE_JOIN_HIT)

        with self._join_stripes[int(key[:8], 16) % _STRIPES]:  # single flight for the join as well
            row = self.backend.get_composite(key)
            if row is not None and tuple(row.prov) == pairs:
                with self._mu:
                    self._stats["join_hits"] += 1
                return self._result(row.payload, kind, label, pairs, SOURCE_JOIN_HIT)
            parts = [Part(d, v, self._component(d, v, spec)[0]) for d, v in pairs]
            payload = self._as_bytes(spec.join(kind, parts))
            with self._mu:
                self._stats["join_computes"] += 1
                if self._all_current(pairs):
                    self.backend.put_composite(key, kind, pairs, payload)
        return self._result(payload, kind, label, pairs, SOURCE_JOINED)

    def _result(self, payload, kind, label, pairs, source) -> Result:
        return Result(payload, kind, label, pairs, source if self.expose_cache_status else None)

    # ------------------------------------------------------------ components
    def _all_current(self, pairs: Sequence[tuple[str, int]]) -> bool:
        return all((m := self._meta.get(d)) is not None and not m.deleted and m.version == v for d, v in pairs)

    @staticmethod
    def _as_bytes(payload) -> bytes:
        if isinstance(payload, str):
            return payload.encode("utf-8")
        if not isinstance(payload, (bytes, bytearray)):
            raise TypeError("artifact payloads must be bytes")
        return bytes(payload)

    def _component(self, doc_id: str, version: int, spec: ArtifactSpec) -> tuple[bytes, bool]:
        """One document's artifact, computed at most once. Returns (payload, computed_now)."""
        with self._mu:
            self._stats["cache_lookups"] += 1
        payload = self.backend.get_component(doc_id, version, spec.kind, spec.version)
        if payload is not None:
            with self._mu:
                self._stats["component_hits"] += 1
            return payload, False
        stripe = self._stripes[int(hashlib.sha256(f'{doc_id}\x00{version}\x00{spec.kind}'.encode()).hexdigest()[:8], 16) % _STRIPES]
        with stripe:  # single flight: concurrent callers wait for one computation
            payload = self.backend.get_component(doc_id, version, spec.kind, spec.version)
            if payload is not None:
                with self._mu:
                    self._stats["component_hits"] += 1
                return payload, False
            text = self.backend.get_doc_text(doc_id, version)
            if text is None:
                raise Refused()  # deleted after the gate
            # The callback sees ONE document and nothing else.
            payload = self._as_bytes(spec.compute(spec.kind, doc_id, version, text))
            with self._mu:
                self._stats["component_computes"] += 1
                if self._all_current([(doc_id, version)]):
                    self.backend.put_component(doc_id, version, spec.kind, spec.version, payload)
            return payload, True

    # ------------------------------------------------------------ housekeeping and numbers
    def sweep(self) -> int:
        """Delete expired leases. Returns how many were removed."""
        now = self.clock.now()
        n = 0
        with self._mu:
            for d in list(self._leases):
                per = self._leases[d]
                for p in [p for p, l in per.items() if l.expires <= now]:
                    del per[p]
                    n += 1
                if not per:
                    del self._leases[d]
        return n

    def stats(self) -> dict:
        """Counters. ``per_user_baseline`` is how many costly computations a
        separate cache per user would have done for the same requests."""
        with self._mu:
            s = dict(self._stats)
            s["per_user_baseline"] = len({(p, d, v, k) for p, d, v, k in self._served})
            s["active_leases"] = sum(len(v) for v in self._leases.values())
        s.update({f"stored_{k}": v for k, v in self.backend.counts().items()})
        base = s["per_user_baseline"]
        s["compute_vs_per_user"] = round(s["component_computes"] / base, 4) if base else None
        return s
