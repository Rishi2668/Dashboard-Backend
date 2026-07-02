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

# Mon–Sat daily vocabulary (repeats every week of the roadmap)
DAILY_VOCAB_DAYS: list[tuple[str, str]] = [
    ("daily_vocab_mon", "Mon"),
    ("daily_vocab_tue", "Tue"),
    ("daily_vocab_wed", "Wed"),
    ("daily_vocab_thu", "Thu"),
    ("daily_vocab_fri", "Fri"),
    ("daily_vocab_sat", "Sat"),
]

# English-only phases — follow this exact order
ENGLISH_PHASES: list[dict] = [
    {
        "id": 1,
        "name": "Grammar Foundation",
        "subtitle": "Parts of Speech → Question Tags",
        "weeks": [1, 2, 3, 4],
        "topics": [
            "Nouns",
            "Pronouns",
            "Adjectives",
            "Verbs",
            "Adverbs",
            "Articles",
            "Prepositions",
            "Conjunctions",
            "Subject-Verb Agreement",
            "Tenses",
            "Active & Passive Voice",
            "Direct & Indirect Speech",
            "Modals",
            "Question Tags",
        ],
    },
    {
        "id": 2,
        "name": "Vocabulary & Usage",
        "subtitle": "Synonyms → Spelling Errors",
        "weeks": [5, 6],
        "topics": [
            "Synonyms",
            "Antonyms",
            "One Word Substitution",
            "Idioms & Phrases",
            "Phrasal Verbs",
            "Homophones & Homonyms",
            "Commonly Confused Words",
            "Spelling Errors",
        ],
    },
    {
        "id": 3,
        "name": "Error Detection",
        "subtitle": "Spotting → Cloze Test",
        "weeks": [7],
        "topics": [
            "Error Spotting",
            "Sentence Improvement",
            "Fill in the Blanks",
            "Cloze Test",
        ],
    },
    {
        "id": 4,
        "name": "Comprehension",
        "subtitle": "Para Jumbles → Reading Comprehension",
        "weeks": [8],
        "topics": [
            "Para Jumbles",
            "Sentence Rearrangement",
            "Reading Comprehension",
        ],
    },
    {
        "id": 5,
        "name": "Revision",
        "subtitle": "PYQ → Full English Revision",
        "weeks": [9, 10],
        "topics": [
            "Topic-wise Previous Year Questions",
            "Mixed Practice Sets",
            "Mock Test Revision",
            "Full English Revision",
        ],
        "virtual": True,
    },
]

# 2.5h daily English block split (shown in English Daily Hub)
ENGLISH_DAILY_BLOCK = [
    {"label": "New words + revision", "minutes": 45, "focus": "vocabulary"},
    {"label": "Grammar / topic of the week", "minutes": 75, "focus": "grammar"},
    {"label": "Practice (PYQ / exercises)", "minutes": 30, "focus": "practice"},
]

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
    "Subject-Verb Agreement": "Subject Verb Agreement",
    "Active & Passive Voice": "Active Passive Voice",
    "Direct & Indirect Speech": "Direct Indirect Speech",
    "Spelling Errors": "Spelling Correction",
    "Topic-wise Previous Year Questions": "Topic-wise PYQ",
    "Mock Test Revision": "Mock Test Revision",
    "Full English Revision": "Full English Revision",
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
        "english_phase": 1,
        "english_phase_note": "Parts of Speech (Nouns → Verbs)",
        "topics": {
            "GS": ["Modern History", "Polity"],
            "English": ["Nouns", "Pronouns", "Adjectives", "Verbs"],
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
        "english_phase": 1,
        "english_phase_note": "Parts of Speech (Adverbs → Conjunctions)",
        "topics": {
            "GS": ["Geography", "Economy"],
            "English": ["Adverbs", "Articles", "Prepositions", "Conjunctions"],
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
        "english_phase": 1,
        "english_phase_note": "Agreement & Tenses",
        "topics": {
            "GS": [],
            "English": ["Subject-Verb Agreement", "Tenses"],
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
        "english_phase": 1,
        "english_phase_note": "Voice, Speech, Modals & Tags",
        "topics": {
            "GS": [],
            "English": [
                "Active & Passive Voice",
                "Direct & Indirect Speech",
                "Modals",
                "Question Tags",
            ],
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
        "english_phase": 2,
        "english_phase_note": "Core vocabulary",
        "topics": {
            "GS": ["Biology", "Physics", "Chemistry"],
            "English": ["Synonyms", "Antonyms", "One Word Substitution", "Idioms & Phrases"],
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
        "english_phase": 2,
        "english_phase_note": "Advanced vocabulary & usage",
        "topics": {
            "GS": ["Computer", "Environment", "Static GK"],
            "English": [
                "Phrasal Verbs",
                "Homophones & Homonyms",
                "Commonly Confused Words",
                "Spelling Errors",
            ],
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
        "english_phase": 3,
        "english_phase_note": "Error detection drills",
        "topics": {
            "GS": [],
            "English": ["Error Spotting", "Sentence Improvement", "Fill in the Blanks", "Cloze Test"],
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
        "english_phase": 4,
        "english_phase_note": "Comprehension focus",
        "topics": {
            "GS": ["Current Affairs"],
            "English": ["Para Jumbles", "Sentence Rearrangement", "Reading Comprehension"],
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
        "english_phase": 5,
        "english_phase_note": "English revision — PYQ & mocks",
        "topics": {
            "GS": ["Static GK"],
            "English": [],
            "Quant": [],
            "Reasoning": [],
        },
        "virtual": [
            "Topic-wise Previous Year Questions",
            "Mixed Practice Sets",
            "Mock Test Revision",
            "Current Affairs Revision",
            "Mixed Practice",
            "Mock Analysis",
        ],
    },
    {
        "number": 10,
        "phase": 3,
        "start": "2026-09-01",
        "end": "2026-09-05",
        "label": "Week 10",
        "english_phase": 5,
        "english_phase_note": "Full English revision",
        "topics": {"GS": [], "English": [], "Quant": [], "Reasoning": []},
        "virtual": [
            "Full English Revision",
            "Complete Revision",
            "Previous Year Questions",
            "Mock Analysis",
            "Weak Topics",
            "Mixed Practice",
            "Formula Revision",
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
    ("english", "Nouns", "very_high"),
    ("english", "Pronouns", "very_high"),
    ("english", "Adjectives", "very_high"),
    ("english", "Verbs", "very_high"),
    ("english", "Adverbs", "very_high"),
    ("english", "Articles", "very_high"),
    ("english", "Prepositions", "very_high"),
    ("english", "Conjunctions", "very_high"),
    ("english", "Subject Verb Agreement", "very_high"),
    ("english", "Tenses", "very_high"),
    ("english", "Active Passive Voice", "high"),
    ("english", "Direct Indirect Speech", "high"),
    ("english", "Modals", "high"),
    ("english", "Question Tags", "high"),
    ("english", "Synonyms", "very_high"),
    ("english", "Antonyms", "very_high"),
    ("english", "Phrasal Verbs", "high"),
    ("english", "Homophones & Homonyms", "medium"),
    ("english", "Commonly Confused Words", "medium"),
    ("english", "Fill in the Blanks", "high"),
    ("english", "Sentence Rearrangement", "medium"),
    ("english", "Topic-wise PYQ", "high"),
    ("english", "Mixed Practice Sets", "high"),
    ("english", "Mock Test Revision", "high"),
    ("english", "Full English Revision", "high"),
    ("gk", "Modern History", "very_high"),
    ("gk", "Environment", "high"),
    ("reasoning", "Clock & Calendar", "high"),
    ("gk", "Complete Revision", "medium"),
    ("quant", "Formula Revision", "medium"),
]
