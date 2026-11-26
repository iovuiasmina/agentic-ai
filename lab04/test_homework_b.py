"""Tests for the Homework B test runner - no model calls. Run: pytest test_homework_b.py -v"""
from homework_b_lessons import extract_code, run_tests

GOOD = '''
from datetime import date

def nights_between(check_in: str, check_out: str) -> int:
    a, b = date.fromisoformat(check_in), date.fromisoformat(check_out)
    if b < a:
        raise ValueError("check-out before check-in")
    return (b - a).days
'''

# A typical first attempt: correct arithmetic, but no error for check-out before check-in.
NO_ORDER_CHECK = '''
from datetime import datetime

def nights_between(check_in, check_out):
    a = datetime.strptime(check_in, "%Y-%m-%d")
    b = datetime.strptime(check_out, "%Y-%m-%d")
    return (b - a).days
'''


def test_a_correct_function_passes():
    ok, out = run_tests(GOOD)
    assert ok, out
    assert "8/8 tests passed" in out


def test_a_missing_check_fails_with_a_readable_message():
    ok, out = run_tests(NO_ORDER_CHECK)
    assert not ok
    assert "FAIL check-out before check-in" in out


def test_an_infinite_loop_is_stopped_by_the_timeout():
    ok, out = run_tests("def nights_between(a, b):\n    while True:\n        pass\n")
    assert not ok and out.startswith("TIMEOUT")


def test_code_is_extracted_from_a_markdown_block():
    assert extract_code("Here you go:\n```python\nx = 1\n```\nDone.") == "x = 1"
