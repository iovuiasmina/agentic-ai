"""Tests for Homework A - no model calls. Run: pytest test_homework_a.py -v"""
from fractions import Fraction

import homework_a_voucher as hw
from homework_a_voucher import Operation, Proposals, Rating, State, apply, is_solution, search


def test_checker_accepts_real_solutions():
    assert is_solution("(13 - 9) * (10 - 4)", [4, 9, 10, 13])
    assert is_solution("5 * (5 - 1 / 5)", [1, 5, 5, 5])  # needs the fraction 24/5


def test_checker_rejects_wrong_value_or_wrong_numbers():
    assert not is_solution("13 + 9 + 4 - 10", [4, 9, 10, 13])   # = 16
    assert not is_solution("4 * 6", [4, 9, 10, 13])             # 24, but not the vouchers
    assert not is_solution("13 + 9 + 4 - 10 + 8", [4, 9, 10, 13])  # an extra number
    assert not is_solution("import os", [4, 9, 10, 13])


def test_apply_computes_in_code_and_rejects_illegal_moves():
    s = State([Fraction(v) for v in (1, 5, 5, 5)], ["1", "5", "5", "5"])
    new = apply(s, Operation(a="1", op="/", b="5"))
    assert sorted(new.values) == [Fraction(1, 5), 5, 5]
    assert apply(s, Operation(a="7", op="+", b="5")) is None    # 7 is not on the table
    assert apply(s, Operation(a="1", op="+", b="1")) is None    # only one 1


class FakeReply:
    def __init__(self, parsed):
        self.parsed, self.in_tokens, self.out_tokens, self.text = parsed, 10, 5, ""


def test_search_finds_24_with_a_scripted_model(monkeypatch):
    """The 'model' proposes a fixed path; the code must compute it and verify the final 24."""
    script = {
        "4 9 10 13": [Operation(a="13", op="-", b="9")],
        "4 10 4": [Operation(a="10", op="-", b="4")],
        "4 6": [Operation(a="4", op="*", b="6")],
    }

    def fake_ask(prompt, *, system=None, schema=None, **_):
        if schema is Proposals:
            nums = prompt.split(": ", 1)[1]
            return FakeReply(Proposals(operations=script.get(nums, [])))
        return FakeReply(Rating(reasoning="test", verdict="likely"))

    monkeypatch.setattr(hw, "ask", fake_ask)
    expr, counts = search([4, 9, 10, 13])
    assert expr is not None and is_solution(expr, [4, 9, 10, 13])
    assert counts.calls == 5  # 3 proposals + 2 ratings (the last state is checked by code)
