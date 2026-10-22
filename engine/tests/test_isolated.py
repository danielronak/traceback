from pymentor.isolated import run_isolated


def test_runs_in_a_subprocess_and_returns_facts():
    result = run_isolated("name = input()\nprint(name + 1)\n", ["Ada"])
    assert result.stdout == "Ada\n"
    assert (result.diagnostic.code, result.diagnostic.line) == ("TypeError", 2)


def test_hard_timeout_kills_a_hung_child():
    # time.sleep never reaches a traced line, so only the hard timeout can stop it.
    result = run_isolated("import time\ntime.sleep(30)\n", hard_timeout=1)
    assert result.diagnostic.code == "Timeout"
    assert result.diagnostic.data["reason"] == "killed"
