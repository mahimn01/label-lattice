"""Labels.

A label says which documents a piece of work was built from. The people who
may see the work are the people who may read every one of those documents:
the overlap (meet) of the documents' audiences.

* Work on one document has a label with one document.
* A join over several documents has a label with all of them.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

from .acl import AclProvider


@dataclass(frozen=True)
class Label:
    docs: frozenset[str]

    @classmethod
    def of(cls, docs: Iterable[str]) -> "Label":
        docs = frozenset(docs)
        if not docs:
            raise ValueError("a label needs at least one document")
        return cls(docs)

    def meet(self, other: "Label") -> "Label":
        """The label of work that combines work under both labels."""
        return Label(self.docs | other.docs)

    def permits(self, acl: AclProvider, principal: str) -> bool:
        """True if the principal may read every document in the label."""
        checks = [acl.can_read(principal, d) for d in sorted(self.docs)]  # no early exit
        return all(checks)

    def audience(self, acl: AclProvider, principals: Iterable[str]) -> frozenset[str]:
        """The principals (out of ``principals``) who may see work under this label."""
        return frozenset(p for p in principals if self.permits(acl, p))

    def __str__(self) -> str:
        return "&".join(sorted(self.docs))
