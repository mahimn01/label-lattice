"""A small demo: six documents, five people, one shared store.

Run it with:  python examples/demo.py

It shows who can read what, how work is shared, and how a revocation works.
Nothing here uses the network. The clock is fake so the output is the same every run.
"""

from pathlib import Path

from labellattice import InMemoryAcl, LmfStore, ManualClock, Refused, answer

DOCS = Path(__file__).parent / "docs"

# Which groups may read each document.
DOC_GROUPS = {
    "handbook": {"all"},
    "onboarding": {"all"},
    "pricing": {"sales", "exec"},
    "roadmap": {"eng", "exec"},
    "legal-review": {"legal", "exec"},
    "merger-plan": {"exec"},
}

# Who is in which group.
PEOPLE = {
    "ana": {"all", "sales"},
    "ben": {"all", "eng"},
    "cleo": {"all", "legal", "exec"},
    "dan": {"all", "exec", "sales"},
    "eve": {"all", "sales"},
}


def heading(text):
    print(f"\n=== {text} ===")


def show(store, user, question):
    print(f"\n{user} asks: {question}")
    a = answer(store, user, question)
    print(f"  documents used: {', '.join(a.sources) or '(none)'}")
    for line in a.text().splitlines():
        print(f"  {line}")


def try_read(store, user, docs):
    try:
        r = store.query(user, docs)
        print(f"  {user} reads {docs}: allowed (label {r.label})")
        return True
    except Refused:
        print(f"  {user} reads {docs}: refused")
        return False


def main():
    clock = ManualClock()
    acl = InMemoryAcl()
    for user, groups in PEOPLE.items():
        acl.add_user(user, groups)
    for doc, groups in DOC_GROUPS.items():
        acl.set_doc_acl(doc, groups)
    store = LmfStore(acl, clock=clock, lease_s=30, eager_kinds=("claims",))

    heading("1. Ingest")
    for doc in sorted(DOC_GROUPS):
        v = store.put_document(doc, (DOCS / f"{doc}.txt").read_text())
        print(f"  {doc}: version {v}, readable by {sorted(DOC_GROUPS[doc])}")
    print(f"  claim lists computed once per document: {store.stats()['component_computes']}")

    heading("2. Different people, different answers")
    show(store, "ana", "What is the Northwind budget?")
    show(store, "ben", "What is the Northwind budget?")
    show(store, "cleo", "What is the Northwind budget?")
    show(store, "ben", "When does the merger close?")
    show(store, "cleo", "When does the merger close?")

    heading("3. A refusal gives away nothing")
    try_read(store, "ben", ["merger-plan"])        # real document, not allowed
    try_read(store, "ben", ["no-such-document"])   # does not exist
    print("  Both refusals look the same. A caller cannot tell a secret from nothing.")

    heading("4. Work is shared")
    for user in ("ana", "dan", "eve"):
        answer(store, user, "What is the Northwind budget?")
    answer(store, "ana", "Is remote work allowed?")
    answer(store, "eve", "Is remote work allowed?")
    s = store.stats()
    print(f"  requests: {s['requests']}   refused: {s['refusals']}")
    print(f"  costly claim lists computed: {s['component_computes']} (one per document)")
    print(f"  what a separate cache for each user would have computed: {s['per_user_baseline']}")
    print(f"  joins computed: {s['join_computes']}   joins reused: {s['join_hits']}")

    heading("5. Revocation: the push path")
    print("  Dan is in the exec group. He reads the merger plan and the pricing sheet.")
    try_read(store, "dan", ["merger-plan", "pricing"])
    print("  The admin removes dan from exec.")
    acl.revoke_membership("dan", "exec")
    try_read(store, "dan", ["merger-plan", "pricing"])
    try_read(store, "dan", ["pricing"])            # dan is still in sales
    print("  Access ended at once. Cleo, still in exec, is not affected and nothing is recomputed:")
    before = store.stats()["component_computes"]
    try_read(store, "cleo", ["merger-plan", "pricing"])
    print(f"  new computations for cleo: {store.stats()['component_computes'] - before}")

    heading("6. Revocation: the push is lost")
    print("  Same idea, but this store never hears about changes. Only leases protect it.")
    clock2 = ManualClock()
    acl2 = InMemoryAcl()
    for user, groups in PEOPLE.items():
        acl2.add_user(user, groups)
    for doc, groups in DOC_GROUPS.items():
        acl2.set_doc_acl(doc, groups)
    lossy = LmfStore(acl2, clock=clock2, lease_s=30, push=False)
    for doc in DOC_GROUPS:
        lossy.put_document(doc, (DOCS / f"{doc}.txt").read_text())
    try_read(lossy, "cleo", ["merger-plan"])
    acl2.revoke_membership("cleo", "exec")
    acl2.revoke_membership("cleo", "legal")
    clock2.advance(29)
    print("  29 seconds later (inside the 30 second lease), the old lease may still work:")
    try_read(lossy, "cleo", ["merger-plan"])
    clock2.advance(2)
    print("  31 seconds later, the lease is over:")
    try_read(lossy, "cleo", ["merger-plan"])
    print("  Worst case staleness is the lease length, never more.")


if __name__ == "__main__":
    main()
