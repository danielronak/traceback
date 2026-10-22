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
