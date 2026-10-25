"""Artifact kinds, the compute callback and the join.

An artifact is the costly work product for ONE document at ONE version. It is a
pure function of that document's text. It never sees any other document.

Three kinds ship by default. All are deterministic and local. None calls a
network or a model.

* ``claims``: the list of statements in the document. The join is a set union,
  so it is exact.
* ``chunk_note``: a short note (word count, top keywords, opening words). The
  join merges notes. It is lossy, as a real summary of notes would be.
* ``kv_segment``: a STAND-IN for a model's KV cache segment. It is a
  deterministic byte string, not real model state. The join concatenates the
  segments and adds a patch digest. It says nothing about the quality of real
  KV patching.

To use a real model, register your own ``ArtifactSpec`` or pass ``compute=``
to the store.
"""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from typing import Callable, NamedTuple, Sequence

KIND_CLAIMS = "claims"
KIND_CHUNK_NOTE = "chunk_note"
KIND_KV_SEGMENT = "kv_segment"


class Part(NamedTuple):
    """One input to a join: a document, its version and its artifact payload."""

    doc_id: str
    version: int
    payload: bytes


# compute(kind, doc_id, version, text) -> payload. Sees one document only.
ComputeFn = Callable[[str, str, int, str], bytes]
# join(kind, parts) -> payload. Parts are sorted by doc id.
JoinFn = Callable[[str, Sequence[Part]], bytes]


@dataclass(frozen=True)
class ArtifactSpec:
    kind: str
    compute: ComputeFn
    join: JoinFn
    # Change this when compute or join changes. It is part of every cache key.
    version: str = "1"


class ArtifactRegistry:
    def __init__(self, specs: Sequence[ArtifactSpec] = ()) -> None:
        self._specs: dict[str, ArtifactSpec] = {}
        for s in specs:
            self.register(s)

    def register(self, spec: ArtifactSpec) -> None:
        self._specs[spec.kind] = spec

    def get(self, kind: str) -> ArtifactSpec:
        try:
            return self._specs[kind]
        except KeyError:
            raise ValueError(f"unknown artifact kind: {kind!r}") from None

    def kinds(self) -> list[str]:
        return sorted(self._specs)

    def with_compute(self, compute: ComputeFn, version: str = "custom") -> "ArtifactRegistry":
        """A copy where every kind uses ``compute``. Joins stay as they were."""
        return ArtifactRegistry(
            [ArtifactSpec(s.kind, compute, s.join, f"{s.version}+{version}") for s in self._specs.values()]
        )

    @classmethod
    def default(cls) -> "ArtifactRegistry":
        return cls(
            [
                ArtifactSpec(KIND_CLAIMS, default_compute, _join_claims),
                ArtifactSpec(KIND_CHUNK_NOTE, default_compute, _join_notes),
                ArtifactSpec(KIND_KV_SEGMENT, default_compute, _join_kv),
            ]
        )


# ---------------------------------------------------------------- helpers

def canonical_json(obj) -> bytes:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("ascii")


def src_tag(doc_id: str, version: int) -> str:
    """The marker that records where a piece of content came from."""
    return f"{doc_id}@{version}"


_SENT = re.compile(r"(?<=[.!?])\s+|\n+")
_WORD = re.compile(r"[a-z0-9']+")
STOPWORDS = frozenset(
    "the a an and or of to in on for with at by from is are was were be been it this that these those "
    "as we our you your they their not no but if then than so do does did has have had will would can "
    "could should may might about into over under per each all any".split()
)


def keywords(text: str) -> list[str]:
    return [w for w in _WORD.findall(text.lower()) if len(w) > 2 and w not in STOPWORDS]


# ---------------------------------------------------------------- default compute

def default_compute(kind: str, doc_id: str, version: int, text: str) -> bytes:
    if kind == KIND_CLAIMS:
        return _compute_claims(doc_id, version, text)
    if kind == KIND_CHUNK_NOTE:
        return _compute_note(doc_id, version, text)
    if kind == KIND_KV_SEGMENT:
        return _compute_kv(doc_id, version, text)
    raise ValueError(f"default compute has no kind {kind!r}")


def _compute_claims(doc_id: str, version: int, text: str) -> bytes:
    tag = src_tag(doc_id, version)
    seen: set[str] = set()
    claims = []
    for s in _SENT.split(text):
        s = " ".join(s.split())
        if s and s not in seen:
            seen.add(s)
            claims.append({"text": s, "srcs": [tag]})
    return canonical_json(claims)


def _compute_note(doc_id: str, version: int, text: str) -> bytes:
    words = keywords(text)
    counts: dict[str, int] = {}
    for w in words:
        counts[w] = counts.get(w, 0) + 1
    top = [w for w, _ in sorted(counts.items(), key=lambda kv: (-kv[1], kv[0]))[:5]]
    lead = " ".join(text.split())[:80]
    return canonical_json(
        {"srcs": [src_tag(doc_id, version)], "words": len(_WORD.findall(text.lower())), "keywords": top, "leads": [lead]}
    )


KV_TOKENS = 64


def _compute_kv(doc_id: str, version: int, text: str) -> bytes:
    tag = src_tag(doc_id, version)
    toks = text.split()[:KV_TOKENS]
    body = b"".join(hashlib.sha256(f"{tag}:{i}:{t}".encode()).digest()[:4] for i, t in enumerate(toks))
    return f"KV1|{tag}|{len(toks)}|".encode("ascii", "backslashreplace") + body


# ---------------------------------------------------------------- default joins

def _join_claims(kind: str, parts: Sequence[Part]) -> bytes:
    merged: dict[str, set[str]] = {}
    order: list[str] = []
    for p in parts:
        for c in json.loads(p.payload):
            if c["text"] not in merged:
                merged[c["text"]] = set()
                order.append(c["text"])
            merged[c["text"]].update(c["srcs"])
    return canonical_json([{"text": t, "srcs": sorted(merged[t])} for t in order])


def _join_notes(kind: str, parts: Sequence[Part]) -> bytes:
    srcs: list[str] = []
    leads: list[str] = []
    kws: list[str] = []
    words = 0
    for p in parts:
        n = json.loads(p.payload)
        srcs += n["srcs"]
        leads += n["leads"]
        words += n["words"]
        for w in n["keywords"]:
            if w not in kws:
                kws.append(w)
    return canonical_json({"srcs": sorted(srcs), "words": words, "keywords": kws[:8], "leads": leads})


def _join_kv(kind: str, parts: Sequence[Part]) -> bytes:
    srcs = ",".join(src_tag(p.doc_id, p.version) for p in parts)
    digest = hashlib.sha256(b"".join(p.payload for p in parts)).digest()[:16]
    return f"KVJ|{srcs}|".encode("ascii", "backslashreplace") + digest + b"".join(p.payload for p in parts)
