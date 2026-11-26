"""Lab 4 - Homework B: learn from a failed test.

    python homework_b_lessons.py              # 5 runs of each strategy
    python homework_b_lessons.py --runs 3     # fewer runs (fewer requests)
    Tests (no model calls): pytest test_homework_b.py -v

The model writes nights_between(check_in, check_out). My own tests decide if it is right.
The generated code runs in a SEPARATE PROCESS with a timeout, in a temporary folder - never inside this harness.
"""
import re
import subprocess
import sys
import tempfile
from pathlib import Path

from llm import QuotaExhausted, ask

MAX_ATTEMPTS = 3
TIMEOUT_S = 10

TASK = (
    "Write a Python function nights_between(check_in: str, check_out: str) -> int that returns the number "
    "of hotel nights between two dates given as 'YYYY-MM-DD'. Use only the standard library. "
    "Reply with the code only, in one ```python block."
)

# My tests, appended after the generated code. They print one line per failure and exit 1 if any failed.
TESTS = r'''

def _expect(name, fn, expected):
    try:
        got = fn()
    except Exception as e:
        got = f"raised {type(e).__name__}: {e}"
    if got != expected:
        print(f"FAIL {name}: expected {expected!r}, got {got!r}")
        return False
    return True


def _expect_error(name, fn):
    try:
        got = fn()
    except Exception:
        return True
    print(f"FAIL {name}: expected an exception, got {got!r}")
    return False


results = [
    _expect("same day", lambda: nights_between("2026-05-12", "2026-05-12"), 0),
    _expect("normal stay", lambda: nights_between("2026-05-12", "2026-05-16"), 4),
    _expect("across a month end", lambda: nights_between("2026-01-30", "2026-02-02"), 3),
    _expect("across a year end", lambda: nights_between("2026-12-30", "2027-01-02"), 3),
    _expect("leap year", lambda: nights_between("2028-02-28", "2028-03-01"), 2),
    _expect_error("check-out before check-in", lambda: nights_between("2026-05-16", "2026-05-12")),
    _expect_error("badly formatted date", lambda: nights_between("12/05/2026", "2026-05-16")),
    _expect_error("impossible date", lambda: nights_between("2026-02-30", "2026-03-02")),
]
print(f"{sum(results)}/{len(results)} tests passed")
raise SystemExit(0 if all(results) else 1)
'''


def extract_code(text: str) -> str:
    m = re.search(r"```(?:python)?\s*\n(.*?)```", text, re.S)
    return (m.group(1) if m else text).strip()


def run_tests(code: str) -> tuple[bool, str]:
    """Run the generated code + my tests in a separate, isolated Python process with a timeout."""
    with tempfile.TemporaryDirectory() as tmp:
        script = Path(tmp) / "candidate_test.py"
        script.write_text(code + "\n" + TESTS, encoding="utf-8")
        try:
            proc = subprocess.run([sys.executable, "-I", str(script)], cwd=tmp, capture_output=True,
                                  text=True, timeout=TIMEOUT_S)
        except subprocess.TimeoutExpired:
            return False, f"TIMEOUT: the code did not finish within {TIMEOUT_S} s"
    output = (proc.stdout + proc.stderr).strip()
    return proc.returncode == 0, output[-1500:]  # keep the end: the summary and the last errors


def plain_retries() -> tuple[bool, int, int]:
    """On failure, just ask again (same prompt)."""
    tokens = 0
    for attempt in range(1, MAX_ATTEMPTS + 1):
        r = ask(TASK, temperature=1.0)
        tokens += r.in_tokens + r.out_tokens
        ok, out = run_tests(extract_code(r.text))
        print(f"   attempt {attempt}: {'PASS' if ok else 'fail'}  ({out.splitlines()[-1] if out else ''})")
        if ok:
            return True, attempt, tokens
    return False, MAX_ATTEMPTS, tokens


def with_lessons() -> tuple[bool, int, int, list[str]]:
    """On failure, the model explains the failure in two sentences; every lesson goes into the next prompt."""
    tokens, lessons = 0, []
    for attempt in range(1, MAX_ATTEMPTS + 1):
        prompt = TASK
        if lessons:
            prompt += "\n\nLessons from your earlier failed attempts (apply all of them):\n" + "\n".join(
                f"- {lesson}" for lesson in lessons)
        r = ask(prompt, temperature=1.0)
        tokens += r.in_tokens + r.out_tokens
        code = extract_code(r.text)
        ok, out = run_tests(code)
        print(f"   attempt {attempt}: {'PASS' if ok else 'fail'}  ({out.splitlines()[-1] if out else ''})")
        if ok:
            return True, attempt, tokens, lessons
        if attempt < MAX_ATTEMPTS:
            reflect = ask(f"Your code:\n```python\n{code}\n```\n\nTest output:\n{out}\n\n"
                          "Why did it fail, and what will you change? Two sentences.", temperature=0.3)
            tokens += reflect.in_tokens + reflect.out_tokens
            lesson = " ".join(reflect.text.split())
            lessons.append(lesson)
            print(f"      lesson: {lesson[:200]}")
    return False, MAX_ATTEMPTS, tokens, lessons


if __name__ == "__main__":
    runs = int(sys.argv[sys.argv.index("--runs") + 1]) if "--runs" in sys.argv else 5
    table = {"plain retries": [], "with lessons": []}
    try:
        for i in range(1, runs + 1):
            print(f"\n== run {i}: plain retries")
            table["plain retries"].append(plain_retries())
            print(f"== run {i}: with lessons")
            ok, attempts, tokens, _ = with_lessons()
            table["with lessons"].append((ok, attempts, tokens))
    except QuotaExhausted as e:
        print(f"\n[stopped] {e}")
    print("\n| strategy | solved | attempts per run | avg attempts | avg tokens |")
    print("|---|---|---|---|---|")
    for name, rows in table.items():
        if rows:
            print(f"| {name} | {sum(r[0] for r in rows)}/{len(rows)} | {[r[1] for r in rows]} "
                  f"| {sum(r[1] for r in rows) / len(rows):.1f} | {sum(r[2] for r in rows) / len(rows):,.0f} |")
