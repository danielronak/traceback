from pymentor.sandbox import RunResult, execute


def test_captures_output_and_echoes_input_like_a_terminal():
    result = execute("name = input('Name? ')\nprint('Hi', name)\n", ["Ada"])
    assert result.diagnostic is None
    assert result.stdout == "Name? Ada\nHi Ada\n"
    assert result.inputs_used == ["Ada"]


def test_input_can_come_from_a_callable():
    prompts = []
    result = execute("print(input('Q? '))\n", lambda prompt: prompts.append(prompt) or "42")
    assert prompts == ["Q? "]
    assert result.stdout.endswith("42\n")


def test_running_out_of_input_is_a_clear_fact():
    d = execute("a = input()\nb = input()\n", ["1"]).diagnostic
    assert (d.code, d.line, d.data["input_exhausted"]) == ("EOFError", 2, True)


def test_error_is_located_at_the_deepest_learner_frame():
    source = "def half(n):\n    return n / 0\n\nhalf(4)\n"
    d = execute(source).diagnostic
    assert (d.code, d.line) == ("ZeroDivisionError", 2)
    assert [f["line"] for f in d.data["frames"]] == [4, 2]


def test_error_inside_python_is_located_in_learner_code():
    d = execute("int('x')\n").diagnostic
    assert (d.code, d.line, d.col) == ("ValueError", 1, 0)


def test_python_suggestions_are_kept_in_the_message():
    d = execute("total = 0\nprint(totl)\n").diagnostic
    assert d.message == "name 'totl' is not defined. Did you mean: 'total'?"
    assert (d.col, d.end_col, d.data["name"]) == (6, 10, "totl")


def test_step_budget_stops_infinite_loops_at_the_looping_line():
    d = execute("n = 0\nwhile n < 5:\n    print(n)\n", step_limit=1_000).diagnostic
    assert (d.code, d.line, d.data["reason"]) == ("Timeout", 3, "steps")


def test_learner_except_cannot_swallow_the_step_budget():
    source = "try:\n    while True:\n        pass\nexcept Exception:\n    print('caught')\n"
    result = execute(source, step_limit=1_000)
    assert result.diagnostic.code == "Timeout"
    assert "caught" not in result.stdout


def test_recursion_points_at_the_repeating_call():
    d = execute("def f():\n    return f()\n\nf()\n").diagnostic
    assert (d.code, d.line) == ("RecursionError", 2)
    assert max(f["repeats"] for f in d.data["frames"]) > 100


def test_exit_ends_the_program_normally():
    result = execute("import sys\nprint('a')\nsys.exit()\nprint('b')\n")
    assert result.diagnostic is None
    assert result.stdout == "a\n"


def test_output_is_capped():
    result = execute("for i in range(100_000):\n    print('xxxxxxxxxx')\n")
    assert len(result.stdout) == 100_000


def test_syntax_errors_are_reported_without_running():
    assert execute("print('a'\n").diagnostic.code == "SyntaxError"


def test_learner_namespace_is_available_for_exercise_tests():
    result = execute("def double(n):\n    return n * 2\n")
    assert result.namespace["double"](4) == 8


def test_result_round_trips_through_json_shape():
    result = execute("print(1/0)\n")
    again = RunResult.from_dict(result.to_dict())
    assert again.diagnostic == result.diagnostic
    assert again.stdout == result.stdout


def test_output_streams_to_a_listener_before_input_waits():
    seen = []

    def answer(prompt):
        seen.append(("waiting", "".join(t for t in seen if isinstance(t, str))))
        return "Ada"

    execute("print('Hi')\nname = input('Name? ')\n", answer, on_output=seen.append)
    assert ("waiting", "Hi\nName? ") in seen


def test_time_spent_waiting_for_input_does_not_count():
    import time

    def slow_typist(prompt):
        time.sleep(0.3)
        return "x"

    # Enough steps that the wall clock is checked after each wait.
    source = "for i in range(3):\n    input()\n    for j in range(10_000):\n        pass\n"
    assert execute(source, slow_typist, time_limit=0.5).diagnostic is None


def test_learner_pressing_stop_is_not_a_crash():
    def stop(prompt):
        raise KeyboardInterrupt

    result = execute("print('a')\ninput()\nprint('b')\n", stop)
    assert result.diagnostic is None and result.interrupted
    assert result.stdout == "a\n"
