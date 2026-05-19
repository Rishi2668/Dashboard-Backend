from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.quote import Quote

QUOTES = [
    ("Discipline is choosing between what you want now and what you want most.", "Unknown", "discipline"),
    ("The only way to do great work is to love what you do.", "Steve Jobs", "hard_work"),
    ("Success is the sum of small efforts repeated day in and day out.", "Robert Collier", "consistency"),
    ("Competition is a byproduct of productive work.", "Unknown", "competition"),
    ("Your mind is a powerful thing. When you fill it with positive thoughts, your life will start to change.", "Unknown", "success_mindset"),
    ("Don't watch the clock; do what it does. Keep going.", "Sam Levenson", "discipline"),
    ("The harder you work for something, the greater you'll feel when you achieve it.", "Unknown", "hard_work"),
    ("Small daily improvements are the key to staggering long-term results.", "Unknown", "consistency"),
    ("Rank is earned in silence, celebrated in results.", "Unknown", "competition"),
    ("Believe you can and you're halfway there.", "Theodore Roosevelt", "success_mindset"),
    ("SSC CGL doesn't test intelligence alone — it tests consistency under pressure.", "Unknown", "competition"),
    ("Every mock test is a mirror. Learn from it, don't fear it.", "Unknown", "success_mindset"),
    ("Revision is not optional. It's the difference between aspirant and selected.", "Unknown", "consistency"),
    ("Wake up with determination. Go to bed with satisfaction.", "Unknown", "discipline"),
    ("Pain of discipline weighs ounces. Pain of regret weighs tons.", "Jim Rohn", "discipline"),
]


async def seed_quotes(db: AsyncSession):
    result = await db.execute(select(Quote).limit(1))
    if result.scalar_one_or_none():
        return
    for text, author, category in QUOTES:
        db.add(Quote(text=text, author=author, category=category))
