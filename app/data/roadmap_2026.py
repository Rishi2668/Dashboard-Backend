"""SSC CGL 2026 roadmap: Jul 1 – Sep 5, phase-wise weekly schedule."""

from __future__ import annotations

from datetime import date

ROADMAP_START = date(2026, 7, 1)
ROADMAP_END = date(2026, 9, 5)
EXAM_LABEL = "SSC CGL 2026"

DAILY_SCHEDULE = {
    "gs_hours": 3.0,
    "english_vocab_hours": 2.5,
    "quant_reasoning_hours": 2.0,
    "study_days": "Mon–Sat",
    "sunday": "Mandatory full mock + analysis",
}

# Map roadmap topic labels → existing syllabus chapter names (when names differ)
CHAPTER_ALIASES: dict[str, str] = {
    "Modern History": "History",
    "Economy": "Economics",
    "Error Spotting": "Error Detection",
    "Pipes & Cisterns": "Pipe & Cistern",
    "Boats & Streams": "Boat & Stream",
    "Height & Distance": "Heights & Distances",
    "Statement & Conclusion": "Statement Conclusion",
    "Computer": "Computer Awareness",
    "Blood Relations": "Blood Relation",
    "Ratio & Proportion": "Ratio and Proportion",
    "Profit & Loss": "Profit and Loss",
    "Simple Interest": "Simple Interest",
    "Compound Interest": "Compound Interest",
    "Time & Work": "Time and Work",
    "Time Speed Distance": "Time Speed Distance",
    "Mixture & Alligation": "Mixture & Alligation",
    "One Word Substitution": "One Word Substitution",
    "Idioms & Phrases": "Idioms & Phrases",
    "Para Jumbles": "Para Jumbles",
    "Cloze Test": "Cloze Test",
    "Synonyms": "Synonyms & Antonyms",
    "Antonyms": "Synonyms & Antonyms",
    "Vocabulary (Daily)": "Vocabulary",
    "Vocabulary Revision": "Vocabulary",
}

# slug on SyllabusSubject
SUBJECT_SLUG = {
    "GS": "gk",
    "English": "english",
    "Quant": "quant",
    "Reasoning": "reasoning",
}

PHASES = [
    {
        "id": 1,
        "name": "Phase 1",
        "subtitle": "High-weightage topics first",
        "weeks": [1, 2, 3, 4],
        "color": "emerald",
    },
    {
        "id": 2,
        "name": "Phase 2",
        "subtitle": "Science, advanced English & reasoning",
        "weeks": [5, 6, 7],
        "color": "blue",
    },
    {
        "id": 3,
        "name": "Phase 3",
        "subtitle": "Complete revision & mocks",
        "weeks": [8, 9, 10],
        "color": "purple",
    },
]

# Virtual tasks (stored in user_roadmap_tasks, not syllabus chapters)
VIRTUAL_TASK_PREFIX = "task:"

WEEKS: list[dict] = [
    {
        "number": 1,
        "phase": 1,
        "start": "2026-07-01",
        "end": "2026-07-06",
        "label": "Week 1",
        "topics": {
            "GS": ["Modern History", "Polity"],
            "English": ["Parts of Speech", "Tenses", "Vocabulary (Daily)"],
            "Quant": ["Percentage", "Ratio & Proportion"],
            "Reasoning": ["Analogy", "Classification"],
        },
    },
    {
        "number": 2,
        "phase": 1,
        "start": "2026-07-07",
        "end": "2026-07-13",
        "label": "Week 2",
        "topics": {
            "GS": ["Geography", "Economy"],
            "English": ["Articles", "Prepositions", "Vocabulary (Daily)"],
            "Quant": ["Average", "Profit & Loss"],
            "Reasoning": ["Series", "Coding Decoding"],
        },
    },
    {
        "number": 3,
        "phase": 1,
        "start": "2026-07-14",
        "end": "2026-07-20",
        "label": "Week 3",
        "topics": {
            "GS": [],
            "English": [
                "Subject Verb Agreement",
                "Error Spotting",
                "Reading Comprehension",
                "Vocabulary (Daily)",
            ],
            "Quant": ["Simple Interest", "Compound Interest", "Time & Work"],
            "Reasoning": ["Blood Relations", "Direction Sense"],
        },
    },
    {
        "number": 4,
        "phase": 1,
        "start": "2026-07-21",
        "end": "2026-07-27",
        "label": "Week 4",
        "topics": {
            "GS": [],
            "English": ["Vocabulary (Daily)"],
            "Quant": [
                "Pipes & Cisterns",
                "Time Speed Distance",
                "Boats & Streams",
                "Mixture & Alligation",
                "Partnership",
            ],
            "Reasoning": [],
        },
    },
    {
        "number": 5,
        "phase": 2,
        "start": "2026-07-28",
        "end": "2026-08-03",
        "label": "Week 5",
        "topics": {
            "GS": ["Biology", "Physics", "Chemistry"],
            "English": ["Idioms & Phrases", "One Word Substitution", "Vocabulary (Daily)"],
            "Quant": ["Algebra"],
            "Reasoning": ["Seating Arrangement"],
        },
    },
    {
        "number": 6,
        "phase": 2,
        "start": "2026-08-04",
        "end": "2026-08-10",
        "label": "Week 6",
        "topics": {
            "GS": ["Computer", "Environment", "Static GK"],
            "English": ["Synonyms", "Antonyms", "Cloze Test", "Vocabulary (Daily)"],
            "Quant": ["Geometry", "Mensuration"],
            "Reasoning": ["Syllogism", "Venn Diagram"],
        },
    },
    {
        "number": 7,
        "phase": 2,
        "start": "2026-08-11",
        "end": "2026-08-17",
        "label": "Week 7",
        "topics": {
            "GS": [],
            "English": ["Para Jumbles", "Vocabulary (Daily)"],
            "Quant": ["Trigonometry", "Height & Distance"],
            "Reasoning": ["Statement & Conclusion", "Clock & Calendar"],
        },
    },
    {
        "number": 8,
        "phase": 3,
        "start": "2026-08-18",
        "end": "2026-08-24",
        "label": "Week 8",
        "topics": {
            "GS": ["Current Affairs"],
            "English": ["Vocabulary Revision"],
            "Quant": ["Formula Revision"],
            "Reasoning": [],
        },
        "virtual": [
            "Complete Revision",
            "Previous Year Questions",
            "Mock Analysis",
            "Weak Topics",
        ],
    },
    {
        "number": 9,
        "phase": 3,
        "start": "2026-08-25",
        "end": "2026-08-31",
        "label": "Week 9",
        "topics": {
            "GS": ["Static GK"],
            "English": ["Vocabulary Revision"],
            "Quant": [],
            "Reasoning": [],
        },
        "virtual": ["Current Affairs Revision", "Mixed Practice", "Mock Analysis"],
    },
    {
        "number": 10,
        "phase": 3,
        "start": "2026-09-01",
        "end": "2026-09-05",
        "label": "Week 10",
        "topics": {"GS": [], "English": [], "Quant": [], "Reasoning": []},
        "virtual": [
            "Complete Revision",
            "Previous Year Questions",
            "Mock Analysis",
            "Weak Topics",
            "Mixed Practice",
            "Formula Revision",
            "Vocabulary Revision",
        ],
    },
]

MOCK_TASKS = [
    {"key": "mandatory_mock", "label": "Mandatory Mock", "required": True},
    {"key": "mock_analysis", "label": "Mock Analysis", "required": True},
    {"key": "optional_mock", "label": "Second Mock (Optional)", "required": False},
]

# Chapters to ensure exist (subject_slug, name, priority)
EXTRA_CHAPTERS: list[tuple[str, str, str]] = [
    ("english", "Parts of Speech", "very_high"),
    ("english", "Tenses", "very_high"),
    ("english", "Articles", "very_high"),
    ("english", "Prepositions", "very_high"),
    ("english", "Subject Verb Agreement", "very_high"),
    ("gk", "Modern History", "very_high"),
    ("gk", "Environment", "high"),
    ("reasoning", "Clock & Calendar", "high"),
    ("gk", "Complete Revision", "medium"),
    ("quant", "Formula Revision", "medium"),
]
