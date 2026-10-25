from labellattice import answer
from tests.conftest import build_world


def test_answer_uses_only_documents_the_asker_may_read():
    _, _, store = build_world()
    a = answer(store, "alice", "When does the merger close?")
    assert a.sources == ("memo",) and "March" in a.text()
    b = answer(store, "bob", "When does the merger close?")
    assert b.lines == () and "merger" not in b.text().lower()
    assert "No answer" in b.text()


def test_budget_question_never_mentions_a_doc_the_asker_cannot_read():
    _, _, store = build_world()
    for user, hidden in (("bob", {"memo", "board"}), ("alice", {"board"}), ("dave", {"memo"})):
        a = answer(store, user, "What is the budget?")
        used = set(a.sources)
        assert used and not (used & hidden)
        for _, srcs in a.lines:
            assert not {s.split("@")[0] for s in srcs} & hidden


def test_equal_audiences_share_the_joined_work():
    _, _, store = build_world()
    answer(store, "alice", "budget")
    before = store.stats()
    answer(store, "carol", "budget")
    after = store.stats()
    assert after["component_computes"] == before["component_computes"]
    assert after["join_computes"] == before["join_computes"]


def test_answers_are_deterministic():
    a = answer(build_world()[2], "alice", "budget merger hours").text()
    b = answer(build_world()[2], "alice", "budget merger hours").text()
    assert a == b


def test_revocation_changes_the_answer_at_once():
    _, acl, store = build_world(lease_s=3600)
    assert "March" in answer(store, "alice", "merger").text()
    acl.revoke_membership("alice", "legal")
    assert "March" not in answer(store, "alice", "merger").text()
