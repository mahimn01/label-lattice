"""A tiny question answerer on top of the store, to show the whole path.

It ranks only the documents the asker may read, using the shared per-document
claim lists. It then joins the best few under their overlap label. It uses
keyword overlap, not a model.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from .artifacts import KIND_CLAIMS, keywords
from .store import LmfStore, Result


@dataclass(frozen=True)
class Answer:
    question: str
    principal: str
    sources: tuple[str, ...]          # documents joined for this answer
    lines: tuple[tuple[str, tuple[str, ...]], ...]  # (claim text, source tags)
    result: Result | None = field(default=None, compare=False)

    def text(self) -> str:
        if not self.lines:
            return "No answer found in the documents you may read."
        return "\n".join(f"- {t}  [{', '.join(s)}]" for t, s in self.lines)


def _score(q_words: set[str], text: str) -> int:
    return len(q_words & set(keywords(text)))


def answer(store: LmfStore, principal: str, question: str, top_k: int = 3, max_lines: int = 5) -> Answer:
    q = set(keywords(question))
    scored: list[tuple[int, str]] = []
    for doc in store.entitled_docs(principal):  # only documents the asker may read
        claims = store.query(principal, [doc], KIND_CLAIMS).json()
        s = sum(_score(q, c["text"]) for c in claims)
        if s > 0:
            scored.append((s, doc))
    scored.sort(key=lambda t: (-t[0], t[1]))
    top = [d for _, d in scored[:top_k]]
    if not top:
        return Answer(question, principal, (), ())
    res = store.query(principal, top, KIND_CLAIMS)  # gated again, cached under the overlap label
    claims = [(c["text"], tuple(c["srcs"])) for c in res.json() if _score(q, c["text"]) > 0]
    claims.sort(key=lambda c: (-_score(q, c[0]), c[0]))
    return Answer(question, principal, tuple(top), tuple(claims[:max_lines]), res)
