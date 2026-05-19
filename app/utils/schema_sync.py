"""Apply lightweight schema updates for existing databases (create_all does not ALTER tables)."""

import logging

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine

logger = logging.getLogger(__name__)

# PostgreSQL: add columns/tables that may be missing after model changes
PATCHES = [
    "ALTER TABLE users ADD COLUMN IF NOT EXISTS target_marks DOUBLE PRECISION",
    "ALTER TABLE users ADD COLUMN IF NOT EXISTS exam_date DATE",
    # Calc practice: ensure counters are never NULL
    "UPDATE calc_weak_area_stats SET total_attempts = 0 WHERE total_attempts IS NULL",
    "UPDATE calc_weak_area_stats SET correct_count = 0 WHERE correct_count IS NULL",
    "UPDATE calc_weak_area_stats SET total_time_ms = 0 WHERE total_time_ms IS NULL",
    "UPDATE calc_practice_sessions SET total_questions = 0 WHERE total_questions IS NULL",
    "UPDATE calc_practice_sessions SET correct_count = 0 WHERE correct_count IS NULL",
    "UPDATE calc_practice_sessions SET skipped_count = 0 WHERE skipped_count IS NULL",
    "UPDATE calc_practice_sessions SET total_time_ms = 0 WHERE total_time_ms IS NULL",
    "UPDATE calc_practice_sessions SET xp_earned = 0 WHERE xp_earned IS NULL",
    # Mock tests: SSC CGL structured fields
    "ALTER TABLE mock_tests ADD COLUMN IF NOT EXISTS test_type VARCHAR(20) DEFAULT 'full'",
    "ALTER TABLE mock_tests ADD COLUMN IF NOT EXISTS total_questions INTEGER DEFAULT 100",
    "ALTER TABLE mock_tests ADD COLUMN IF NOT EXISTS reasoning_max_marks DOUBLE PRECISION DEFAULT 50",
    "ALTER TABLE mock_tests ADD COLUMN IF NOT EXISTS reasoning_total_questions INTEGER DEFAULT 25",
    "ALTER TABLE mock_tests ADD COLUMN IF NOT EXISTS reasoning_attempted INTEGER DEFAULT 0",
    "ALTER TABLE mock_tests ADD COLUMN IF NOT EXISTS reasoning_correct INTEGER DEFAULT 0",
    "ALTER TABLE mock_tests ADD COLUMN IF NOT EXISTS reasoning_wrong INTEGER DEFAULT 0",
    "ALTER TABLE mock_tests ADD COLUMN IF NOT EXISTS quant_max_marks DOUBLE PRECISION DEFAULT 50",
    "ALTER TABLE mock_tests ADD COLUMN IF NOT EXISTS quant_total_questions INTEGER DEFAULT 25",
    "ALTER TABLE mock_tests ADD COLUMN IF NOT EXISTS quant_attempted INTEGER DEFAULT 0",
    "ALTER TABLE mock_tests ADD COLUMN IF NOT EXISTS quant_correct INTEGER DEFAULT 0",
    "ALTER TABLE mock_tests ADD COLUMN IF NOT EXISTS quant_wrong INTEGER DEFAULT 0",
    "ALTER TABLE mock_tests ADD COLUMN IF NOT EXISTS english_max_marks DOUBLE PRECISION DEFAULT 50",
    "ALTER TABLE mock_tests ADD COLUMN IF NOT EXISTS english_total_questions INTEGER DEFAULT 25",
    "ALTER TABLE mock_tests ADD COLUMN IF NOT EXISTS english_attempted INTEGER DEFAULT 0",
    "ALTER TABLE mock_tests ADD COLUMN IF NOT EXISTS english_correct INTEGER DEFAULT 0",
    "ALTER TABLE mock_tests ADD COLUMN IF NOT EXISTS english_wrong INTEGER DEFAULT 0",
    "ALTER TABLE mock_tests ADD COLUMN IF NOT EXISTS gk_max_marks DOUBLE PRECISION DEFAULT 50",
    "ALTER TABLE mock_tests ADD COLUMN IF NOT EXISTS gk_total_questions INTEGER DEFAULT 25",
    "ALTER TABLE mock_tests ADD COLUMN IF NOT EXISTS gk_attempted INTEGER DEFAULT 0",
    "ALTER TABLE mock_tests ADD COLUMN IF NOT EXISTS gk_correct INTEGER DEFAULT 0",
    "ALTER TABLE mock_tests ADD COLUMN IF NOT EXISTS gk_wrong INTEGER DEFAULT 0",
]


async def sync_schema(engine: AsyncEngine) -> None:
    applied = 0
    for stmt in PATCHES:
        try:
            async with engine.begin() as conn:
                await conn.execute(text(stmt))
            applied += 1
        except Exception as exc:
            logger.debug("Schema patch skipped: %s — %s", stmt[:60], exc)
    logger.info("Schema sync completed (%d/%d patches)", applied, len(PATCHES))
