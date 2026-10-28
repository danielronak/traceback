from pymentor.features import extract
from pymentor.sandbox import execute


def features_for(source, inputs=None):
    diagnostic = execute(source, inputs, step_limit=5_000).diagnostic
    return extract(diagnostic, source)


def test_typo_of_a_learner_name():
    f = features_for("total = 0\nprint(totl)\n")
    assert f["similar_name"] == "total"
    assert f["builtin_name"] is None


def test_misspelled_builtin_and_missing_import():
    assert features_for("pritn('x')\n")["builtin_name"] == "print"
    assert features_for("print(math.pi)\n")["module"] == "math"


def test_name_defined_later_or_inside_a_function():
    assert features_for("print(score)\nscore = 1\n")["defined_later"] is True
    f = features_for("def f():\n    secret = 1\n\nf()\nprint(secret)\n")
    assert f["defined_in_function"] == "f"
    assert f["defined_later"] is False


def test_bare_word_in_print():
    f = features_for("print(hello)\n")
    assert (f["in_print"], f["word_like"], f["defined_anywhere"]) == (True, True, False)


def test_input_source_is_found_anywhere_in_the_expression():
    f = features_for("age = input()\nprint('Next: ' + age + 1)\n", ["4"])
    assert (f["input_name"], f["input_line"]) == ("age", 1)


def test_loop_whose_condition_never_changes():
    f = features_for("count = 0\nwhile count < 3:\n    print('hi')\n")
    assert (f["loop_line"], f["unchanged_names"]) == (2, "count")
    f = features_for("items = [1]\nwhile items:\n    items.append(1)\n")
    assert f["unchanged_names"] is None  # a method call may change it


def test_in_place_method_result():
    f = features_for("nums = [2, 1]\nordered = nums.sort()\nordered.append(3)\n")
    assert (f["none_name"], f["inplace_method"], f["inplace_line"]) == ("ordered", "sort", 2)


def test_strings_side_by_side_in_brackets_were_meant_as_two():
    found = features_for('jobs = ["wash up" "homework"]\njobs.remove("homework")\n')
    assert found["joined_line"] == 1 and found["joined_text"] == '"wash up" "homework"'
    # Text split over lines on purpose is the feature's legitimate use.
    split = features_for('label = ("Total: "\n         "items")\nprint(label + 1)\n')
    assert "joined_line" not in split


def test_text_added_to_a_number_is_a_label_unless_it_holds_a_number():
    assert features_for('print(len([1]) + " items")\n')["text_literal"] == '" items"'
    assert features_for('print(5 + "7")\n')["text_literal"] is None
