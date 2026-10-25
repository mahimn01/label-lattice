import importlib.util
from pathlib import Path

DEMO = Path(__file__).resolve().parent.parent / "examples" / "demo.py"


def run(capsys):
    spec = importlib.util.spec_from_file_location("ll_demo", DEMO)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    mod.main()
    return capsys.readouterr().out


def test_demo_runs_and_tells_the_story(capsys):
    out = run(capsys)
    assert "ben reads ['merger-plan']: refused" in out
    assert "ben reads ['no-such-document']: refused" in out
    assert "dan reads ['merger-plan', 'pricing']: refused" in out
    assert "new computations for cleo: 0" in out
    assert "31 seconds later, the lease is over:\n  cleo reads ['merger-plan']: refused" in out
    # ben must never see the merger plan or the CEO news
    ben_part = out.split("ben asks: When does the merger close?")[1].split("cleo asks")[0]
    assert "Contoso" not in ben_part and "CEO" not in ben_part


def test_demo_output_is_the_same_every_run(capsys):
    assert run(capsys) == run(capsys)
