"""Lab 4 - Homework A: the voucher puzzle (24 with four vouchers).

    python homework_a_voucher.py            # both puzzles: direct answers vs search
    python homework_a_voucher.py direct     # only the direct answers
    python homework_a_voucher.py search     # only the search
    Tests (no model calls): pytest test_homework_a.py -v

Direct: ask the model 5 times for an expression; my code checks every answer exactly.
Search: the model PROPOSES operations and RATES states; my code does every calculation and the final check.
"""
import ast
import re
import sys
from collections import Counter
from dataclasses import dataclass, field
from fractions import Fraction
from typing import Literal

from pydantic import BaseModel, Field

from llm import QuotaExhausted, ask

TARGET = Fraction(24)
PUZZLES = [[4, 9, 10, 13], [1, 5, 5, 5]]  # both are solvable; the second one needs a fraction
BEAM = 3                                  # how many states survive each step


# --------------------------------------------------------------------------
# Exact checking in code (the same idea as Experiment 2's bonus)
# --------------------------------------------------------------------------
def evaluate(expr: str) -> Fraction | None:
    """Exact, safe arithmetic: numbers, + - * / and parentheses only. Never eval()."""
    ops = {ast.Add: lambda a, b: a + b, ast.Sub: lambda a, b: a - b,
           ast.Mult: lambda a, b: a * b, ast.Div: lambda a, b: a / b}

    def walk(node):
        if isinstance(node, ast.BinOp) and type(node.op) in ops:
            return ops[type(node.op)](walk(node.left), walk(node.right))
        if isinstance(node, ast.Constant) and isinstance(node.value, int):
            return Fraction(node.value)
        raise ValueError("not allowed")
    try:
        return walk(ast.parse(expr, mode="eval").body)
    except (ValueError, SyntaxError, ZeroDivisionError):
        return None


def numbers_used(expr: str) -> list[int] | None:
    try:
        tree = ast.parse(expr, mode="eval")
    except SyntaxError:
        return None
    return sorted(n.value for n in ast.walk(tree) if isinstance(n, ast.Constant))


def is_solution(expr: str, vouchers: list[int]) -> bool:
    """Right value AND every voucher used exactly once (no extra numbers)."""
    return numbers_used(expr) == sorted(vouchers) and evaluate(expr) == TARGET


def clean(expr: str) -> str:
    return expr.strip().strip("`").replace("×", "*").replace("÷", "/").replace("−", "-")


# --------------------------------------------------------------------------
# 1. Direct: one call, one answer
# --------------------------------------------------------------------------
def direct_prompt(vouchers: list[int]) -> str:
    return (f"Use the numbers {' '.join(map(str, vouchers))} to make exactly 24. Use each number exactly once, "
            "combined with + - * / and parentheses. End with exactly this line: Expression: <expression>")


def run_direct(vouchers: list[int], n: int = 5) -> tuple[int, int, int]:
    correct = tokens = 0
    for _ in range(n):
        r = ask(direct_prompt(vouchers), temperature=0.7)
        tokens += r.in_tokens + r.out_tokens
        m = re.search(r"Expression:\s*(.+)", r.text.replace("**", ""))
        expr = clean(m.group(1)) if m else ""
        ok = is_solution(expr, vouchers)
        correct += ok
        print(f"   {'ok   ' if ok else 'WRONG'} {expr[:50]:<50} = {evaluate(expr)}")
    return correct, n, tokens


# --------------------------------------------------------------------------
# 2. Search: the model proposes and rates, my code computes
# --------------------------------------------------------------------------
@dataclass
class State:
    values: list[Fraction]          # numbers still left
    exprs: list[str]                # how each number was built
    history: list[str] = field(default_factory=list)

    def key(self) -> tuple:
        return tuple(sorted(self.values))

    def show(self) -> str:
        return " ".join(str(v) for v in self.values)


class Operation(BaseModel):
    a: str = Field(description="A number from the list, exactly as written (fractions as 5/3)")
    op: Literal["+", "-", "*", "/"]
    b: str = Field(description="Another number from the list, exactly as written")


class Proposals(BaseModel):
    operations: list[Operation] = Field(description="Exactly 3 different promising operations")


class Rating(BaseModel):
    reasoning: str = Field(description="One short sentence: can these numbers still reach 24?")
    verdict: Literal["sure", "likely", "impossible"]


PROPOSE = ("You help solve the 24 game. Given the numbers left, propose exactly 3 different operations, "
           "each combining TWO of the numbers into one with + - * or /. Choose the ones most likely to still "
           "reach exactly 24 using all numbers. Write the numbers exactly as given (fractions as 5/3).")
VALUE = ("You judge a state of the 24 game: can the numbers left still be combined, each used exactly once, "
         "with + - * / into exactly 24? Answer sure, likely or impossible.")
RANK = {"sure": 0, "likely": 1, "impossible": 2}


def apply(state: State, op: Operation) -> State | None:
    """My code does the arithmetic. Returns None if the operation is not legal for this state."""
    try:
        a, b = Fraction(op.a.strip()), Fraction(op.b.strip())
    except (ValueError, ZeroDivisionError):
        return None
    values, exprs = list(state.values), list(state.exprs)
    if a not in values:
        return None
    i = values.index(a)
    ea = exprs[i]
    del values[i], exprs[i]
    if b not in values:
        return None
    j = values.index(b)
    eb = exprs[j]
    del values[j], exprs[j]
    if op.op == "/" and b == 0:
        return None
    result = {"+": a + b, "-": a - b, "*": a * b, "/": a / b if b else None}[op.op]
    return State(values + [result], exprs + [f"({ea} {op.op} {eb})"],
                 state.history + [f"{a} {op.op} {b} = {result}"])


@dataclass
class Counts:
    calls: int = 0
    tokens: int = 0


def propose(state: State, counts: Counts) -> list[State]:
    r = ask(f"Numbers left: {state.show()}", system=PROPOSE, schema=Proposals, temperature=0.7)
    counts.calls += 1
    counts.tokens += r.in_tokens + r.out_tokens
    if r.parsed is None:
        return []
    return [s for op in r.parsed.operations if (s := apply(state, op)) is not None]


def value(state: State, counts: Counts) -> str:
    if len(state.values) == 1:  # one number left: code knows the answer, no model call needed
        return "sure" if state.values[0] == TARGET else "impossible"
    r = ask(f"Numbers left: {state.show()}", system=VALUE, schema=Rating)
    counts.calls += 1
    counts.tokens += r.in_tokens + r.out_tokens
    return r.parsed.verdict if r.parsed else "impossible"


def search(vouchers: list[int]) -> tuple[str | None, Counts]:
    counts = Counts()
    frontier = [State([Fraction(v) for v in vouchers], [str(v) for v in vouchers])]
    for step in range(1, 4):
        candidates, seen = [], set()
        for state in frontier:
            for new in propose(state, counts):
                if new.key() not in seen:  # the same numbers reached twice: rate them once
                    seen.add(new.key())
                    candidates.append(new)
        rated = sorted(((value(c, counts), c) for c in candidates), key=lambda vc: RANK[vc[0]])
        frontier = [c for v, c in rated if v != "impossible"][:BEAM] or [c for _, c in rated][:BEAM]
        print(f"   step {step}: {len(candidates)} candidates -> keep "
              + ", ".join(f"[{c.show()}]" for c in frontier))
        if not frontier:
            break
    for state in frontier:
        if len(state.values) == 1 and state.values[0] == TARGET:
            expr = state.exprs[0][1:-1]  # drop the outer parentheses
            assert is_solution(expr, vouchers), expr  # the code checks the search too
            return expr, counts
    return None, counts


if __name__ == "__main__":
    which = sys.argv[1] if len(sys.argv) > 1 else "both"
    summary = []
    try:
        for vouchers in PUZZLES:
            name = " ".join(map(str, vouchers))
            if which in ("both", "direct"):
                print(f"\n== direct, {name}")
                ok, n, tok = run_direct(vouchers)
                summary.append((name, "direct (5 tries)", f"{ok}/{n}", n, tok))
            if which in ("both", "search"):
                print(f"\n== search, {name}")
                expr, c = search(vouchers)
                print(f"   result: {expr or 'no solution found'}")
                summary.append((name, "search", "solved" if expr else "failed", c.calls, c.tokens))
    except QuotaExhausted as e:
        print(f"\n[stopped] {e}")
    print("\n| vouchers | approach | result | model calls | tokens (in + out) |")
    print("|---|---|---|---|---|")
    for row in summary:
        print(f"| {row[0]} | {row[1]} | {row[2]} | {row[3]} | {row[4]:,} |")
