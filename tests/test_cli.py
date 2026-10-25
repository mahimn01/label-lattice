import subprocess
import sys

import pytest

from labellattice.cli import EXIT_REFUSED, main


@pytest.fixture
def home(tmp_path):
    h = str(tmp_path / "ll")
    assert main(["--home", h, "init"]) == 0
    for args in (
        ["acl", "add-user", "alice", "--groups", "all,legal"],
        ["acl", "add-user", "bob", "--groups", "all"],
        ["put", "memo", "--text", "The merger closes in March. Budget is 5 million.", "--groups", "legal"],
        ["put", "handbook", "--text", "Work hours are nine to five. Budget is 5 million.", "--groups", "all"],
    ):
        assert main(["--home", h, *args]) == 0
    return h


def test_ask_as_each_user(home, capsys):
    capsys.readouterr()
    assert main(["--home", home, "ask", "--as", "alice", "When does the merger close?"]) == 0
    assert "March" in capsys.readouterr().out
    assert main(["--home", home, "ask", "--as", "bob", "When does the merger close?"]) == 0
    out = capsys.readouterr().out
    assert "March" not in out and "No answer" in out


def test_refusal_exit_code_and_message(home, capsys):
    capsys.readouterr()
    assert main(["--home", home, "read", "--as", "bob", "memo"]) == EXIT_REFUSED
    cap = capsys.readouterr()
    assert cap.out == "" and cap.err.strip() == "refused"
    assert main(["--home", home, "read", "--as", "bob", "no-such-doc"]) == EXIT_REFUSED
    assert capsys.readouterr().err.strip() == "refused"


def test_revoke_takes_effect_in_the_next_command(home, capsys):
    assert main(["--home", home, "read", "--as", "alice", "memo"]) == 0
    assert main(["--home", home, "acl", "revoke", "alice", "legal"]) == 0
    assert main(["--home", home, "read", "--as", "alice", "memo"]) == EXIT_REFUSED


def test_query_and_docs_and_update(home, capsys):
    capsys.readouterr()
    assert main(["--home", home, "query", "--as", "alice", "memo", "handbook"]) == 0
    assert "Budget is 5 million." in capsys.readouterr().out
    assert main(["--home", home, "put", "memo", "--text", "The merger is off."]) == 0
    assert "version 2" in capsys.readouterr().out
    assert main(["--home", home, "docs"]) == 0
    assert "memo\tversion 2" in capsys.readouterr().out
    assert main(["--home", home, "delete", "memo"]) == 0
    assert main(["--home", home, "read", "--as", "alice", "memo"]) == EXIT_REFUSED


def test_missing_state_gives_a_helpful_error(tmp_path):
    with pytest.raises(SystemExit) as e:
        main(["--home", str(tmp_path / "none"), "docs"])
    assert "init" in str(e.value)


def test_runs_as_a_module(tmp_path):
    h = str(tmp_path / "m")
    r = subprocess.run([sys.executable, "-m", "labellattice", "--home", h, "init"], capture_output=True, text=True)
    assert r.returncode == 0 and "ready" in r.stdout
