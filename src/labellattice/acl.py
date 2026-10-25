"""ACL providers: the one place that says who may read which document.

The store never decides access by itself. It asks a provider. A provider has
three jobs:

* ``can_read(principal, doc_id)``: may this principal read this document now?
* ``epoch()``: a number that goes up on every ACL change.
* ``subscribe(callback)``: optional push. Called with an ``AclChange`` after a
  change, so the store can drop cached decisions at once. A provider that does
  not push still works: the store then relies on lease expiry alone.
"""

from __future__ import annotations

import threading
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Callable, Iterable


@dataclass(frozen=True)
class AclChange:
    """What an ACL change may have taken away.

    ``docs`` is the set of documents affected, or None for all documents.
    ``principals`` is the set of principals affected, or None for all of them.
    """

    docs: frozenset[str] | None
    principals: frozenset[str] | None
    epoch: int


ChangeCallback = Callable[[AclChange], None]


class AclProvider(ABC):
    @abstractmethod
    def can_read(self, principal: str, doc_id: str) -> bool:
        """True only if ``principal`` may read ``doc_id`` right now."""

    @abstractmethod
    def epoch(self) -> int:
        """Goes up on every ACL change. Must never go down."""

    def subscribe(self, callback: ChangeCallback) -> Callable[[], None]:
        """Register for push notices. Returns a function that unsubscribes.

        The default does nothing, which means "no push".
        """
        return lambda: None


class InMemoryAcl(AclProvider):
    """Groups and per-document ACLs held in memory. Thread safe.

    A principal may read a document if one of the principal's groups is in the
    document's ACL. A document with no ACL can be read by nobody.
    """

    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._members: dict[str, set[str]] = {}
        self._doc_acl: dict[str, set[str]] = {}
        self._epoch = 0
        self._listeners: list[ChangeCallback] = []

    # ---- reads
    def can_read(self, principal: str, doc_id: str) -> bool:
        with self._lock:
            return bool(self._members.get(principal, set()) & self._doc_acl.get(doc_id, set()))

    def epoch(self) -> int:
        with self._lock:
            return self._epoch

    def groups_of(self, principal: str) -> frozenset[str]:
        with self._lock:
            return frozenset(self._members.get(principal, set()))

    def doc_acl(self, doc_id: str) -> frozenset[str]:
        with self._lock:
            return frozenset(self._doc_acl.get(doc_id, set()))

    def users(self) -> list[str]:
        with self._lock:
            return sorted(self._members)

    def audience(self, doc_id: str, principals: Iterable[str] | None = None) -> frozenset[str]:
        """Principals (among ``principals`` or all known users) who may read ``doc_id``."""
        with self._lock:
            pool = list(principals) if principals is not None else list(self._members)
            return frozenset(p for p in pool if self.can_read(p, doc_id))

    # ---- writes (each one bumps the epoch and pushes a change notice)
    def add_user(self, principal: str, groups: Iterable[str] = ()) -> None:
        with self._lock:
            self._members[principal] = set(groups)
            change = self._bump(None, frozenset({principal}))
        self._notify(change)

    def grant_membership(self, principal: str, group: str) -> None:
        with self._lock:
            self._members.setdefault(principal, set()).add(group)
            change = self._bump(frozenset(), frozenset({principal}))
        self._notify(change)

    def revoke_membership(self, principal: str, group: str) -> None:
        with self._lock:
            self._members.setdefault(principal, set()).discard(group)
            affected = frozenset(d for d, acl in self._doc_acl.items() if group in acl)
            change = self._bump(affected, frozenset({principal}))
        self._notify(change)

    def remove_user(self, principal: str) -> None:
        with self._lock:
            self._members.pop(principal, None)
            change = self._bump(None, frozenset({principal}))
        self._notify(change)

    def set_doc_acl(self, doc_id: str, groups: Iterable[str]) -> None:
        with self._lock:
            self._doc_acl[doc_id] = set(groups)
            change = self._bump(frozenset({doc_id}), None)
        self._notify(change)

    def remove_doc_acl(self, doc_id: str) -> None:
        with self._lock:
            self._doc_acl.pop(doc_id, None)
            change = self._bump(frozenset({doc_id}), None)
        self._notify(change)

    # ---- push
    def subscribe(self, callback: ChangeCallback) -> Callable[[], None]:
        with self._lock:
            self._listeners.append(callback)

        def unsubscribe() -> None:
            with self._lock:
                if callback in self._listeners:
                    self._listeners.remove(callback)

        return unsubscribe

    def _bump(self, docs: frozenset[str] | None, principals: frozenset[str] | None) -> AclChange:
        self._epoch += 1
        return AclChange(docs=docs, principals=principals, epoch=self._epoch)

    def _notify(self, change: AclChange) -> None:
        # Called after the lock is released, so a listener may call back in.
        with self._lock:
            listeners = list(self._listeners)
        for cb in listeners:
            cb(change)

    # ---- snapshot (used by the CLI)
    def to_dict(self) -> dict:
        with self._lock:
            return {
                "epoch": self._epoch,
                "users": {u: sorted(g) for u, g in sorted(self._members.items())},
                "docs": {d: sorted(g) for d, g in sorted(self._doc_acl.items())},
            }

    @classmethod
    def from_dict(cls, data: dict) -> "InMemoryAcl":
        acl = cls()
        acl._epoch = int(data.get("epoch", 0))
        acl._members = {u: set(g) for u, g in data.get("users", {}).items()}
        acl._doc_acl = {d: set(g) for d, g in data.get("docs", {}).items()}
        return acl
