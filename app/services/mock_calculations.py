"""SSC CGL mock test calculations (Tier-1 style: 0.5 negative per wrong)."""

NEGATIVE_PER_WRONG = 0.5

SUBJECT_KEYS = ("reasoning", "quant", "english", "gk")


def section_wrong(attempted: int, correct: int, wrong: int | None = None) -> int:
    if wrong is not None:
        return max(0, wrong)
    return max(0, attempted - correct)


def section_accuracy(attempted: int, correct: int) -> float:
    if attempted <= 0:
        return 0.0
    return round(correct / attempted * 100, 1)


def section_negative(wrong: int) -> float:
    return round(wrong * NEGATIVE_PER_WRONG, 2)


def overall_from_sections(sections: list[dict]) -> dict:
    attempted = sum(s.get("attempted", 0) for s in sections)
    correct = sum(s.get("correct", 0) for s in sections)
    wrong = sum(s.get("wrong", 0) for s in sections)
    secured = sum(s.get("secured_marks", 0) for s in sections)
    max_marks = sum(s.get("max_marks", 0) for s in sections)
    total_q = sum(s.get("total_questions", 0) for s in sections)
    return {
        "attempted": attempted,
        "correct": correct,
        "wrong": wrong,
        "total_score": secured,
        "max_score": max_marks,
        "total_questions": total_q,
        "accuracy": section_accuracy(attempted, correct),
        "negative_marks": section_negative(wrong),
    }
