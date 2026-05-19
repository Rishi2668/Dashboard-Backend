"""Rule-based SSC CGL calculation question generator — answers validated before return."""

from __future__ import annotations

import ast
import hashlib
import math
import operator
import random
import uuid
from dataclasses import dataclass
from fractions import Fraction
from typing import Callable

PRACTICE_TYPES = [
    "addition",
    "subtraction",
    "multiplication",
    "division",
    "percentage",
    "squares",
    "cube_roots",
    "square_roots",
    "mixed",
]

DIFFICULTIES = ["easy", "medium", "hard"]

_SAFE_OPS = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
    ast.FloorDiv: operator.floordiv,
    ast.Pow: operator.pow,
    ast.USub: operator.neg,
    ast.UAdd: operator.pos,
}


def _safe_eval(expr: str) -> float:
    node = ast.parse(expr.strip(), mode="eval")

    def _eval(n: ast.AST) -> float:
        if isinstance(n, ast.Expression):
            return _eval(n.body)
        if isinstance(n, ast.Constant) and isinstance(n.value, (int, float)):
            return float(n.value)
        if isinstance(n, ast.BinOp) and type(n.op) in _SAFE_OPS:
            return _SAFE_OPS[type(n.op)](_eval(n.left), _eval(n.right))
        if isinstance(n, ast.UnaryOp) and type(n.op) in _SAFE_OPS:
            return _SAFE_OPS[type(n.op)](_eval(n.operand))
        raise ValueError("Unsupported expression")

    return _eval(node)


def _round_answer(val: float) -> float:
    if abs(val - round(val)) < 1e-9:
        return float(int(round(val)))
    return round(val, 2)


def _fingerprint(text: str, answer: float) -> str:
    raw = f"{text}|{answer}"
    return hashlib.sha256(raw.encode()).hexdigest()[:32]


@dataclass
class GeneratedQuestion:
    question_id: str
    practice_type: str
    difficulty: str
    question_text: str
    correct_answer: float
    answer_tolerance: float
    explanation: str
    fingerprint: str
    display_answer: str


class CalcQuestionGenerator:
    def __init__(self, seed: int | None = None):
        self._rng = random.Random(seed)

    def generate(
        self,
        practice_type: str,
        difficulty: str,
        exclude_fingerprints: set[str] | None = None,
        max_tries: int = 50,
    ) -> GeneratedQuestion:
        exclude = exclude_fingerprints or set()
        resolved_type = practice_type
        if practice_type == "mixed":
            resolved_type = self._rng.choice(
                [t for t in PRACTICE_TYPES if t not in ("mixed",)]
            )

        for _ in range(max_tries):
            q = self._generate_one(resolved_type, difficulty)
            if q.fingerprint not in exclude:
                return q
        return self._generate_one(resolved_type, difficulty)

    def _generate_one(self, practice_type: str, difficulty: str) -> GeneratedQuestion:
        builders: dict[str, Callable[[str], tuple[str, float, str]]] = {
            "addition": self._addition,
            "subtraction": self._subtraction,
            "multiplication": self._multiplication,
            "division": self._division,
            "percentage": self._percentage,
            "squares": self._squares,
            "cube_roots": self._cube_roots,
            "square_roots": self._square_roots,
            "simplification": self._simplification,
            "bodmas": self._bodmas,
            "fractions": self._fractions,
            "decimals": self._decimals,
            "average": self._average,
            "ratio": self._ratio,
        }
        builder = builders.get(practice_type, self._addition)
        text, answer, explanation = builder(difficulty)
        answer = _round_answer(answer)
        tol = 0.01 if isinstance(answer, float) and answer != int(answer) else 0.0
        fp = _fingerprint(text, answer)
        display = str(int(answer)) if answer == int(answer) else f"{answer:.2f}".rstrip("0").rstrip(".")
        return GeneratedQuestion(
            question_id=str(uuid.uuid4()),
            practice_type=practice_type,
            difficulty=difficulty,
            question_text=text,
            correct_answer=answer,
            answer_tolerance=tol,
            explanation=explanation,
            fingerprint=fp,
            display_answer=display,
        )

    def _range(self, difficulty: str) -> tuple[int, int]:
        if difficulty == "easy":
            return (2, 99)
        if difficulty == "hard":
            return (50, 9999)
        return (10, 999)

    def _pick(self, lo: int, hi: int) -> int:
        return self._rng.randint(lo, hi)

    def _addition(self, d: str) -> tuple[str, float, str]:
        lo, hi = self._range(d)
        a, b = self._pick(lo, hi), self._pick(lo, hi)
        ans = a + b
        return f"{a} + {b} = ?", float(ans), f"{a} + {b} = {ans}"

    def _subtraction(self, d: str) -> tuple[str, float, str]:
        lo, hi = self._range(d)
        a, b = self._pick(lo, hi), self._pick(lo, hi)
        if b > a:
            a, b = b, a
        ans = a - b
        return f"{a} − {b} = ?", float(ans), f"{a} − {b} = {ans}"

    def _multiplication(self, d: str) -> tuple[str, float, str]:
        if d == "easy":
            a, b = self._pick(2, 25), self._pick(2, 25)
        elif d == "hard":
            a, b = self._pick(25, 199), self._pick(12, 99)
        else:
            a, b = self._pick(5, 99), self._pick(5, 49)
        ans = a * b
        return f"{a} × {b} = ?", float(ans), f"{a} × {b} = {ans}"

    def _division(self, d: str) -> tuple[str, float, str]:
        if d == "easy":
            b = self._pick(2, 12)
            q = self._pick(2, 25)
        elif d == "hard":
            b = self._pick(7, 99)
            q = self._pick(10, 199)
        else:
            b = self._pick(3, 25)
            q = self._pick(5, 99)
        a = b * q
        return f"{a} ÷ {b} = ?", float(q), f"{a} ÷ {b} = {q}"

    def _percentage(self, d: str) -> tuple[str, float, str]:
        pcts = [5, 10, 12.5, 15, 20, 25, 30, 40, 50, 75] if d != "hard" else [8, 12, 15, 18, 22, 33, 37.5, 45, 62.5, 87.5]
        pct = self._rng.choice(pcts)
        if d == "easy":
            base = self._pick(20, 500) * 4
        elif d == "hard":
            base = self._pick(50, 800) * 4
        else:
            base = self._pick(20, 300) * 4
        ans = base * pct / 100
        ans = _round_answer(ans)
        return (
            f"Find {pct}% of {base}",
            ans,
            f"{pct}% of {base} = ({base} × {pct}) / 100 = {ans}",
        )

    def _squares(self, d: str) -> tuple[str, float, str]:
        if d == "easy":
            n = self._pick(2, 25)
        elif d == "hard":
            n = self._pick(25, 99)
        else:
            n = self._pick(10, 40)
        ans = n * n
        return f"{n}² = ?", float(ans), f"{n}² = {n} × {n} = {ans}"

    def _square_roots(self, d: str) -> tuple[str, float, str]:
        if d == "easy":
            n = self._pick(2, 20)
        elif d == "hard":
            n = self._pick(20, 50)
        else:
            n = self._pick(5, 30)
        val = n * n
        return f"√{val} = ?", float(n), f"√{val} = {n} (since {n}² = {val})"

    def _cube_roots(self, d: str) -> tuple[str, float, str]:
        if d == "easy":
            n = self._pick(2, 10)
        elif d == "hard":
            n = self._pick(10, 30)
        else:
            n = self._pick(3, 15)
        val = n ** 3
        return f"∛{val} = ?", float(n), f"∛{val} = {n} (since {n}³ = {val})"

    def _simplification(self, d: str) -> tuple[str, float, str]:
        return self._bodmas(d)

    def _bodmas(self, d: str) -> tuple[str, float, str]:
        if d == "easy":
            a, b, c = self._pick(2, 30), self._pick(2, 12), self._pick(2, 20)
            expr = f"{a} + {b} × {c}"
        elif d == "hard":
            a = self._pick(10, 80)
            b, c = self._pick(5, 25), self._pick(5, 25)
            d2, e = self._pick(2, 15), self._pick(2, 30)
            expr = f"({a} + {b}) × {c} ÷ {d2} + {e}"
        else:
            a, b, c = self._pick(10, 60), self._pick(2, 15), self._pick(2, 12)
            d2 = self._pick(2, 9)
            expr = f"{a} ÷ {d2} × {b} + {c}"
        expr_display = expr.replace("*", "×").replace("/", "÷") + " = ?"
        py_expr = expr.replace("÷", "/").replace("×", "*")
        ans = _safe_eval(py_expr)
        ans = _round_answer(ans)
        return expr_display, ans, f"{expr_display[:-4]} = {ans}"

    def _fractions(self, d: str) -> tuple[str, float, str]:
        if d == "easy":
            n1, d1 = self._pick(1, 9), self._pick(2, 9)
            n2, d2 = self._pick(1, 9), self._pick(2, 9)
        else:
            n1, d1 = self._pick(2, 19), self._pick(3, 19)
            n2, d2 = self._pick(2, 19), self._pick(3, 19)
        op = self._rng.choice(["+", "−"])
        f1, f2 = Fraction(n1, d1), Fraction(n2, d2)
        result = f1 + f2 if op == "+" else f1 - f2
        ans = float(result)
        if result.denominator == 1:
            ans = float(result.numerator)
        else:
            ans = _round_answer(float(result))
        return (
            f"{n1}/{d1} {op} {n2}/{d2} = ? (decimal)",
            ans,
            f"= {result.numerator}/{result.denominator} ≈ {ans}",
        )

    def _decimals(self, d: str) -> tuple[str, float, str]:
        if d == "easy":
            a = round(self._rng.uniform(1, 50), 1)
            b = round(self._rng.uniform(1, 50), 1)
        else:
            a = round(self._rng.uniform(10, 200), 2)
            b = round(self._rng.uniform(10, 200), 2)
        op = self._rng.choice(["+", "−", "×"])
        if op == "+":
            ans = round(a + b, 2)
            text = f"{a} + {b} = ?"
        elif op == "−":
            if b > a:
                a, b = b, a
            ans = round(a - b, 2)
            text = f"{a} − {b} = ?"
        else:
            ans = round(a * b, 2)
            text = f"{a} × {b} = ?"
        return text, ans, f"{text[:-4]} = {ans}"

    def _average(self, d: str) -> tuple[str, float, str]:
        count = 3 if d == "easy" else (5 if d == "medium" else 6)
        lo, hi = self._range(d)
        nums = [self._pick(lo, hi) for _ in range(count)]
        ans = _round_answer(sum(nums) / count)
        joined = ", ".join(str(n) for n in nums)
        return f"Average of {joined} = ?", ans, f"Sum = {sum(nums)}, ÷ {count} = {ans}"

    def _ratio(self, d: str) -> tuple[str, float, str]:
        if d == "easy":
            a, b = self._pick(2, 12), self._pick(2, 12)
            mult = self._pick(2, 20)
        else:
            a, b = self._pick(3, 25), self._pick(3, 25)
            mult = self._pick(5, 50)
        total = (a + b) * mult
        part = self._rng.choice(["first", "second"])
        if part == "first":
            ans = a * mult
            label = f"first part ({a}:{b})"
        else:
            ans = b * mult
            label = f"second part ({a}:{b})"
        return (
            f"Divide {total} in ratio {a}:{b}. Find the {label}.",
            float(ans),
            f"Total parts = {a + b}, one part = {mult}, answer = {ans}",
        )


def validate_user_answer(correct: float, user_value: float, tolerance: float = 0.01) -> bool:
    if tolerance <= 0:
        return abs(correct - user_value) < 1e-6
    return abs(correct - user_value) <= max(tolerance, 0.01 * abs(correct))
