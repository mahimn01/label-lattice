"""Command line tool. State lives in a folder: ``store.db`` and ``acl.json``.

Example::

    python -m labellattice --home .ll init
    python -m labellattice --home .ll acl add-user alice --groups all,legal
    python -m labellattice --home .ll put memo --text "The merger closes in March." --groups legal
    python -m labellattice --home .ll ask --as alice "When does the merger close?"
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

from .acl import InMemoryAcl
from .errors import Refused
from .search import answer
from .sqlite_backend import SqliteBackend
from .store import LmfStore

EXIT_REFUSED = 3


def _groups(value: str | None) -> list[str]:
    return [g for g in (value or "").split(",") if g]


def _paths(home: str) -> tuple[Path, Path]:
    h = Path(home)
    return h / "store.db", h / "acl.json"


def _load_acl(acl_path: Path) -> InMemoryAcl:
    if not acl_path.exists():
        raise SystemExit(f"no state in {acl_path.parent}; run: python -m labellattice --home {acl_path.parent} init")
    return InMemoryAcl.from_dict(json.loads(acl_path.read_text()))


def _save_acl(acl: InMemoryAcl, acl_path: Path) -> None:
    tmp = acl_path.with_suffix(".tmp")
    tmp.write_text(json.dumps(acl.to_dict(), indent=1, sort_keys=True))
    os.replace(tmp, acl_path)


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="labellattice", description="Label-Lattice memoization with Lazy-Meet Factoring.")
    p.add_argument("--home", default=os.environ.get("LABELLATTICE_HOME", ".labellattice"),
                   help="state folder (default: .labellattice or $LABELLATTICE_HOME)")
    sub = p.add_subparsers(dest="cmd", required=True)
    sub.add_parser("init", help="create an empty state folder")

    acl = sub.add_parser("acl", help="change users, groups and document ACLs").add_subparsers(dest="acl_cmd", required=True)
    a = acl.add_parser("add-user"); a.add_argument("user"); a.add_argument("--groups", default="")
    a = acl.add_parser("grant"); a.add_argument("user"); a.add_argument("group")
    a = acl.add_parser("revoke"); a.add_argument("user"); a.add_argument("group")
    a = acl.add_parser("remove-user"); a.add_argument("user")
    a = acl.add_parser("set-doc"); a.add_argument("doc"); a.add_argument("--groups", required=True)
    acl.add_parser("show")

    a = sub.add_parser("put", help="add or update a document")
    a.add_argument("doc"); a.add_argument("--file"); a.add_argument("--text"); a.add_argument("--groups")
    a = sub.add_parser("delete", help="delete a document"); a.add_argument("doc")
    sub.add_parser("docs", help="admin view: list documents and versions")

    a = sub.add_parser("read", help="read a document as a user"); a.add_argument("--as", dest="user", required=True); a.add_argument("doc")
    a = sub.add_parser("query", help="get the joined artifact over documents, as a user")
    a.add_argument("--as", dest="user", required=True); a.add_argument("--kind", default="claims"); a.add_argument("docs", nargs="+")
    a = sub.add_parser("ask", help="ask a question, as a user")
    a.add_argument("--as", dest="user", required=True); a.add_argument("--top-k", type=int, default=3); a.add_argument("question", nargs="+")
    sub.add_parser("stats", help="show counters for this process")
    return p


def _print_payload(kind: str, payload: bytes) -> None:
    if kind == "kv_segment":
        print(f"{len(payload)} bytes, starts with {payload[:48]!r}")
    else:
        print(json.dumps(json.loads(payload), indent=1, sort_keys=True))


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    db_path, acl_path = _paths(args.home)

    if args.cmd == "init":
        Path(args.home).mkdir(parents=True, exist_ok=True)
        if not acl_path.exists():
            _save_acl(InMemoryAcl(), acl_path)
        SqliteBackend(str(db_path)).close()
        print(f"ready: {args.home}")
        return 0

    acl = _load_acl(acl_path)

    if args.cmd == "acl":
        c = args.acl_cmd
        if c == "show":
            print(json.dumps(acl.to_dict(), indent=1, sort_keys=True))
            return 0
        if c == "add-user": acl.add_user(args.user, _groups(args.groups))
        elif c == "grant": acl.grant_membership(args.user, args.group)
        elif c == "revoke": acl.revoke_membership(args.user, args.group)
        elif c == "remove-user": acl.remove_user(args.user)
        elif c == "set-doc": acl.set_doc_acl(args.doc, _groups(args.groups))
        _save_acl(acl, acl_path)
        print(f"ok (acl epoch {acl.epoch()})")
        return 0

    with LmfStore(acl, backend=SqliteBackend(str(db_path)), eager_kinds=("claims",)) as store:
        if args.cmd == "put":
            if args.file: text = Path(args.file).read_text()
            elif args.text is not None: text = args.text
            else: text = sys.stdin.read()
            if args.groups is not None:
                acl.set_doc_acl(args.doc, _groups(args.groups))
                _save_acl(acl, acl_path)
            v = store.put_document(args.doc, text)
            print(f"{args.doc} is at version {v}")
        elif args.cmd == "delete":
            print("deleted" if store.delete_document(args.doc) else "no such document")
        elif args.cmd == "docs":
            for d, v in store.documents().items():
                print(f"{d}\tversion {v}\tacl {','.join(sorted(acl.doc_acl(d))) or '(none)'}")
        elif args.cmd == "stats":
            print(json.dumps(store.stats(), indent=1, sort_keys=True))
        else:
            try:
                if args.cmd == "read":
                    print(store.read_document(args.user, args.doc))
                elif args.cmd == "query":
                    r = store.query(args.user, args.docs, args.kind)
                    print(f"label: {r.label}   versions: {dict(r.versions)}   source: {r.source}")
                    _print_payload(r.kind, r.payload)
                elif args.cmd == "ask":
                    ans = answer(store, args.user, " ".join(args.question), top_k=args.top_k)
                    print(f"documents used: {', '.join(ans.sources) or '(none)'}")
                    print(ans.text())
            except Refused:
                print("refused", file=sys.stderr)
                return EXIT_REFUSED
    return 0


if __name__ == "__main__":
    sys.exit(main())
