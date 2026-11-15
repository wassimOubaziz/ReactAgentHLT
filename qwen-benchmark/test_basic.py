import pytest

from agent import parse_answer
from data import load_gsm8k
from focused_react import FocusedReActAgent
from metrics import em, f1, gsm8k_correct, precision, recall
from react import parse_finish, parse_step
from tools import Search, calculate


def test_em_ignores_case_articles_and_punctuation():
    assert em("The Eiffel Tower!", "eiffel tower") == 1.0
    assert em("Paris", "London") == 0.0


def test_token_precision_recall_f1():
    assert precision("the big red dog", "big dog") == pytest.approx(2 / 3)
    assert recall("the big red dog", "big dog") == 1.0
    assert f1("the big red dog", "big dog") == pytest.approx(0.8)


def test_yes_no_mismatch_scores_zero():
    assert f1("yes", "no") == 0.0
    assert f1("yes", "yes") == 1.0


def test_gsm8k_numeric_match_uses_last_number():
    assert gsm8k_correct("So the total is $1,200.", "1200")
    assert not gsm8k_correct("The answer is 18 and 20", "18")
    assert not gsm8k_correct("no number here", "5")


def test_calculator_values_and_errors():
    assert calculate("$1,200 / 4") == "300"
    assert calculate("0.1 + 0.2") == "0.3"
    assert calculate("1/0").startswith("Error:")
    assert calculate("__import__('os')").startswith("Error:")


def test_viewer_retrieval_widens_to_ten_but_agent_keeps_top_three():
    paras = [(f"Doc {i}", f"alpha beta gamma {i}") for i in range(12)]
    search = Search(paras, kind="sparse", k=3)
    assert len(search.retrieve("alpha beta")) == 10
    assert len(search("alpha beta").splitlines()) == 3


def test_react_parser_takes_first_action_and_drops_hallucinated_observation():
    text = "Thought: I should search it.\nAction: Search[Colorado orogeny]\nObservation: made up\nThought: next\nAction: Finish[x]"
    assert parse_step(text, ["Search", "Finish"]) == ("I should search it.", ("Search", "Colorado orogeny"))


def test_react_parser_rejects_unknown_or_missing_action():
    assert parse_step("Thought: hmm\nAction: Lookup[x]", ["Search", "Finish"])[1] is None
    assert parse_step("Thought: no action here", ["Search", "Finish"])[1] is None


def test_finish_parser_accepts_missing_prefix_and_rejects_placeholders():
    assert parse_finish("Thought: done.\nAction: Finish[Delhi]") == "Delhi"
    assert parse_finish("The answer is Paris.\nFinish[Paris]") == "Paris"
    assert parse_finish("Action: Finish[<final answer>]") is None
    assert parse_finish("Action: Calculate[3 + 4]") is None


def test_standard_and_cot_answer_parser():
    assert parse_answer("Let me think.\nAnswer: Delhi", "hotpotqa") == ("Delhi", True)
    assert parse_answer("Paris is the capital\nRichard Nixon", "hotpotqa") == ("Richard Nixon", False)
    assert parse_answer("so 3 + 4 = 7 apples", "gsm8k") == ("7", False)


def test_focused_early_stop_rules():
    agent = FocusedReActAgent(None, "hotpotqa", {})
    assert agent.should_stop([("Search", "a"), ("Search", "a")]) == "early_stop"
    assert agent.should_stop([None, None]) == "early_stop"
    assert agent.should_stop([("Search", "a"), ("Search", "b")]) is None
    assert agent.should_stop([("Search", str(i)) for i in range(7)]) == "max_steps"


def test_sample_is_prefix_stable():
    assert load_gsm8k(5) == load_gsm8k(10)[:5]
