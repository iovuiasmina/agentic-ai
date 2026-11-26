"""Lab 4 - Experiment 2: the budget question.

    python exp2_budget.py           # the short prompt vs the better prompt (+ the vote, bonus 1)
    python exp2_budget.py --code    # bonus 2: the model writes the arithmetic, my code computes it
"""
import ast
import operator
import re
import sys
from collections import Counter
from fractions import Fraction

from llm import ask

TRIP = (
    "Two friends fly from Iasi to Rome. Flights cost EUR 129 per person, each way. "
    "They share one hotel room at EUR 85 per night, arriving on 12 May and leaving on 16 May. "
    "The city tax is EUR 2.50 per person per night. Each of them buys a EUR 45 museum pass. "
    "Their total budget is EUR 1000. Does the trip fit the budget, and by how much?"
)
EXPECTED = ("yes", 34.0)  # 516 flights + 340 hotel + 20 tax + 90 passes = 966
FORMAT = "Answer: <yes|no>, <difference in EUR>"

# The short prompt: same output line, no room to work.
SHORT = TRIP + f"\nReply with exactly one line and nothing else: {FORMAT}"

# The better prompt: the same question, but the model may work step by step BEFORE the answer line.
# The last line stays identical, so parse() still works.
BETTER = TRIP + (
    "\nWork it out step by step first: count the nights, then compute each cost separately "
    "(flights, hotel, city tax, museum passes), add them up, and compare the total with the budget. "
    f"Show your working. Then end with exactly this line, and nothing after it: {FORMAT}"
)

# Bonus 2: the model does NOT calculate. It only writes the arithmetic, and evaluate() computes it exactly.
EXPRESSION_ONLY = TRIP + (
    "\nDo NOT calculate anything yourself. Briefly explain what each cost is, then write ONE arithmetic "
    "expression for the total cost of the trip, using only numbers, + - * / and parentheses "
    "(no units, no currency signs, no variable names). "
    "End with exactly this line, and nothing after it: Total: <expression>"
)

ANSWER_RE = re.compile(r"Answer:\s*(yes|no)\s*,\s*(?:EUR|€)?\s*([\d.,]+)", re.I)


def number(text: str) -> float:
    """'34', '34.00', '1,034' and the European '34,00' all become numbers."""
    if re.fullmatch(r"\d+,\d{1,2}", text):
        text = text.replace(",", ".")
    return float(text.replace(",", ""))


def parse(text: str) -> tuple[str, float] | None:
    m = ANSWER_RE.search(text.replace("*", ""))  # models like **Answer:**
    if not m:
        return None
    return m.group(1).lower(), number(m.group(2).rstrip("."))


OPS = {ast.Add: operator.add, ast.Sub: operator.sub, ast.Mult: operator.mul, ast.Div: operator.truediv}


def evaluate(expr: str) -> Fraction | None:
    """Exact, safe arithmetic: numbers, + - * / and parentheses only. Never eval()."""
    def walk(node):
        if isinstance(node, ast.BinOp) and type(node.op) in OPS:
            return OPS[type(node.op)](walk(node.left), walk(node.right))
        if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)):
            return Fraction(str(node.value))
        raise ValueError("not allowed")
    try:
        return walk(ast.parse(expr, mode="eval").body)
    except (ValueError, SyntaxError, ZeroDivisionError):
        return None


def run(prompt: str, n: int = 5) -> list:
    rows = []
    for _ in range(n):
        r = ask(prompt, temperature=0.7)
        rows.append((parse(r.text), r.out_tokens, r.text.strip().splitlines()[-1][:60]))
    return rows


def vote(rows) -> tuple[str, float] | None:
    """Bonus 1: majority vote over the parsed answers (unparseable answers do not vote)."""
    counts = Counter(p for p, _, _ in rows if p is not None)
    if not counts:
        return None
    answer, _ = counts.most_common(1)[0]
    return answer


def run_code(n: int = 5) -> None:
    correct = 0
    tokens = 0
    for _ in range(n):
        r = ask(EXPRESSION_ONLY, temperature=0.7)
        tokens += r.out_tokens
        text = r.text.replace("**", "").replace("×", "*")  # drop Markdown bold, keep the * of multiplication
        m = re.search(r"Total:\s*(.+)", text)
        total = evaluate(m.group(1).strip().strip("`")) if m else None
        verdict = None if total is None else ("yes" if total <= 1000 else "no", float(abs(1000 - total)))
        correct += verdict == EXPECTED
        print(f"   {r.out_tokens:>5} tok   total = {total if total is None else float(total)}   -> {verdict}")
    print(f"== code computes: {correct}/{n} correct, {tokens / n:.0f} output tokens on average")


if __name__ == "__main__":
    if "--code" in sys.argv:
        run_code()
        sys.exit()
    for name, prompt in [("short", SHORT), ("better", BETTER)]:
        rows = run(prompt)
        correct = sum(1 for p, _, _ in rows if p == EXPECTED)
        tokens = sum(t for _, t, _ in rows) / len(rows)
        parsed = sum(1 for p, _, _ in rows if p is not None)
        print(f"\n== {name}: {correct}/{len(rows)} correct, {parsed}/{len(rows)} parsed, "
              f"{tokens:.0f} output tokens on average")
        for p, t, last in rows:
            print(f"   {str(p):<22} {t:>5} tok   last line: {last}")
        winner = vote(rows)
        print(f"   vote picks: {winner} -> {'correct' if winner == EXPECTED else 'WRONG'}")
