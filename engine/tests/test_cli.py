import json

from pymentor.__main__ import main


def test_cli_reports_and_exits_nonzero_on_blocking_errors(tmp_path, capsys):
    program = tmp_path / "broken.py"
    program.write_text("if True\n    print('x')\n")
    assert main(["check", str(program)]) == 1
    assert "Missing colon on line 1" in capsys.readouterr().out


def test_cli_runs_with_input_and_prints_json(tmp_path, capsys):
    program = tmp_path / "ok.py"
    program.write_text("print(input())\n")
    assert main(["check", str(program), "--run", "--input", "hi", "--json"]) == 0
    report = json.loads(capsys.readouterr().out)
    assert report["stdout"] == "hi\nhi\n" and report["findings"] == []


def test_cli_runs_an_exercise_against_a_file_or_its_starter(tmp_path, capsys):
    exercise = tmp_path / "double.toml"
    exercise.write_text(
        'id = "double"\ntitle = "Double it"\nprompt = ""\n'
        'starter = "def double(n):\\n    print(n * 2)\\n"\n'
        'solution = "def double(n):\\n    return n * 2\\n"\n'
        'tests = [{ call = "double(4)", expect = "8" }]\n'
    )
    assert main(["exercise", str(exercise)]) == 1
    out = capsys.readouterr().out
    assert "FAIL  double(4): expected 8, got None" in out
    assert "prints the answer instead of returning it" in out
    answer = tmp_path / "answer.py"
    answer.write_text("def double(n):\n    return n * 2\n")
    assert main(["exercise", str(exercise), str(answer)]) == 0
    assert "All tests pass!" in capsys.readouterr().out
