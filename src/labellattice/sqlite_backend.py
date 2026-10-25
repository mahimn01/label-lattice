"""On-disk backend using the standard library's sqlite3. No extra packages.

One process at a time should own a database file. Leases are not stored: after
a restart every principal is checked again, which is the safe direction.
"""

from __future__ import annotations

import json
import sqlite3
import threading
from typing import Sequence

from .errors import LabelLatticeError
from .backend import Backend, CompositeRow, DocRow

SCHEMA_VERSION = "1"

_SCHEMA = """
CREATE TABLE IF NOT EXISTS meta (k TEXT PRIMARY KEY, v TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS docs (
    doc_id TEXT NOT NULL, version INTEGER NOT NULL, sha TEXT NOT NULL, text TEXT,
    PRIMARY KEY (doc_id, version));
CREATE TABLE IF NOT EXISTS doc_state (doc_id TEXT PRIMARY KEY, deleted INTEGER NOT NULL);
CREATE TABLE IF NOT EXISTS components (
    doc_id TEXT NOT NULL, version INTEGER NOT NULL, kind TEXT NOT NULL, spec_version TEXT NOT NULL,
    payload BLOB NOT NULL, PRIMARY KEY (doc_id, version, kind, spec_version));
CREATE TABLE IF NOT EXISTS composites (
    key TEXT PRIMARY KEY, kind TEXT NOT NULL, prov TEXT NOT NULL, payload BLOB NOT NULL);
CREATE TABLE IF NOT EXISTS composite_docs (
    key TEXT NOT NULL, doc_id TEXT NOT NULL, version INTEGER NOT NULL, PRIMARY KEY (key, doc_id));
CREATE INDEX IF NOT EXISTS composite_docs_by_doc ON composite_docs (doc_id);
"""


class SqliteBackend(Backend):
    def __init__(self, path: str) -> None:
        self._lock = threading.RLock()
        self._db = sqlite3.connect(path, check_same_thread=False, isolation_level=None)
        with self._lock:
            if path != ":memory:":
                self._db.execute("PRAGMA journal_mode=WAL")
                self._db.execute("PRAGMA synchronous=NORMAL")
            self._db.executescript(_SCHEMA)
            row = self._db.execute("SELECT v FROM meta WHERE k='schema'").fetchone()
            if row is None:
                self._db.execute("INSERT INTO meta (k, v) VALUES ('schema', ?)", (SCHEMA_VERSION,))
            elif row[0] != SCHEMA_VERSION:
                self._db.close()
                raise LabelLatticeError(f"unsupported database schema version {row[0]!r}")

    def _tx(self):
        return _Tx(self._db, self._lock)

    # ---- documents
    def load_docs(self) -> list[DocRow]:
        with self._lock:
            rows = self._db.execute(
                "SELECT d.doc_id, d.version, d.sha, COALESCE(s.deleted, 0) FROM docs d "
                "LEFT JOIN doc_state s ON s.doc_id = d.doc_id "
                "WHERE d.version = (SELECT MAX(version) FROM docs WHERE doc_id = d.doc_id) ORDER BY d.doc_id"
            ).fetchall()
        return [DocRow(r[0], r[1], r[2], bool(r[3])) for r in rows]

    def add_doc_version(self, doc_id, version, text, sha):
        with self._tx() as db:
            db.execute("INSERT INTO docs (doc_id, version, sha, text) VALUES (?, ?, ?, ?)", (doc_id, version, sha, text))
            db.execute("INSERT INTO doc_state (doc_id, deleted) VALUES (?, 0) "
                       "ON CONFLICT(doc_id) DO UPDATE SET deleted = 0", (doc_id,))

    def get_doc_text(self, doc_id, version):
        with self._lock:
            row = self._db.execute("SELECT text FROM docs WHERE doc_id=? AND version=?", (doc_id, version)).fetchone()
        return row[0] if row else None

    def doc_versions(self, doc_id):
        with self._lock:
            rows = self._db.execute("SELECT version FROM docs WHERE doc_id=? ORDER BY version", (doc_id,)).fetchall()
        return [r[0] for r in rows]

    def mark_deleted(self, doc_id):
        with self._tx() as db:
            db.execute("UPDATE docs SET text=NULL WHERE doc_id=?", (doc_id,))
            db.execute("INSERT INTO doc_state (doc_id, deleted) VALUES (?, 1) "
                       "ON CONFLICT(doc_id) DO UPDATE SET deleted = 1", (doc_id,))

    # ---- artifact caches
    def get_component(self, doc_id, version, kind, spec_version):
        with self._lock:
            row = self._db.execute(
                "SELECT payload FROM components WHERE doc_id=? AND version=? AND kind=? AND spec_version=?",
                (doc_id, version, kind, spec_version),
            ).fetchone()
        return bytes(row[0]) if row else None

    def put_component(self, doc_id, version, kind, spec_version, payload):
        with self._tx() as db:
            db.execute(
                "INSERT OR REPLACE INTO components (doc_id, version, kind, spec_version, payload) VALUES (?,?,?,?,?)",
                (doc_id, version, kind, spec_version, payload),
            )

    def get_composite(self, key):
        with self._lock:
            row = self._db.execute("SELECT prov, payload FROM composites WHERE key=?", (key,)).fetchone()
        if not row:
            return None
        prov = tuple((d, int(v)) for d, v in json.loads(row[0]))
        return CompositeRow(prov, bytes(row[1]))

    def put_composite(self, key, kind, prov, payload):
        prov = [(d, int(v)) for d, v in prov]
        with self._tx() as db:
            db.execute("DELETE FROM composite_docs WHERE key=?", (key,))
            db.execute("INSERT OR REPLACE INTO composites (key, kind, prov, payload) VALUES (?,?,?,?)",
                       (key, kind, json.dumps(prov), payload))
            db.executemany("INSERT INTO composite_docs (key, doc_id, version) VALUES (?,?,?)",
                           [(key, d, v) for d, v in prov])

    def purge_artifacts(self, doc_id, keep_version):
        keep = -1 if keep_version is None else keep_version
        with self._tx() as db:
            db.execute("DELETE FROM components WHERE doc_id=? AND version<>?", (doc_id, keep))
            keys = [r[0] for r in db.execute(
                "SELECT DISTINCT key FROM composite_docs WHERE doc_id=? AND version<>?", (doc_id, keep))]
            for k in keys:
                db.execute("DELETE FROM composites WHERE key=?", (k,))
                db.execute("DELETE FROM composite_docs WHERE key=?", (k,))

    def counts(self):
        with self._lock:
            q = lambda t: self._db.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0]  # noqa: E731
            return {"doc_versions": q("docs"), "components": q("components"), "composites": q("composites")}

    def close(self):
        with self._lock:
            self._db.close()


class _Tx:
    """BEGIN ... COMMIT under the backend lock. Rolls back on error."""

    def __init__(self, db: sqlite3.Connection, lock: threading.RLock) -> None:
        self._db, self._lock = db, lock

    def __enter__(self):
        self._lock.acquire()
        try:
            self._db.execute("BEGIN IMMEDIATE")
        except BaseException:
            self._lock.release()
            raise
        return self._db

    def __exit__(self, exc_type, exc, tb):
        try:
            self._db.execute("ROLLBACK" if exc_type else "COMMIT")
        finally:
            self._lock.release()
        return False
