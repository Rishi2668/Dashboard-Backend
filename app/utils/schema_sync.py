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
    "ALTER TABLE mock_tests ADD COLUMN IF NOT EXISTS section_subject VARCHAR(20)",
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
    # Re-tag single-subject rows that were saved as full mocks (sectionals)
    """UPDATE mock_tests SET test_type = 'sectional', section_subject = 'reasoning'
       WHERE (test_type IS NULL OR test_type = 'full')
       AND COALESCE(reasoning_attempted, 0) > 0
       AND COALESCE(quant_attempted, 0) = 0 AND COALESCE(english_attempted, 0) = 0 AND COALESCE(gk_attempted, 0) = 0""",
    """UPDATE mock_tests SET test_type = 'sectional', section_subject = 'quant'
       WHERE (test_type IS NULL OR test_type = 'full')
       AND COALESCE(quant_attempted, 0) > 0
       AND COALESCE(reasoning_attempted, 0) = 0 AND COALESCE(english_attempted, 0) = 0 AND COALESCE(gk_attempted, 0) = 0""",
    """UPDATE mock_tests SET test_type = 'sectional', section_subject = 'english'
       WHERE (test_type IS NULL OR test_type = 'full')
       AND COALESCE(english_attempted, 0) > 0
       AND COALESCE(reasoning_attempted, 0) = 0 AND COALESCE(quant_attempted, 0) = 0 AND COALESCE(gk_attempted, 0) = 0""",
    """UPDATE mock_tests SET test_type = 'sectional', section_subject = 'gk'
       WHERE (test_type IS NULL OR test_type = 'full')
       AND COALESCE(gk_attempted, 0) > 0
       AND COALESCE(reasoning_attempted, 0) = 0 AND COALESCE(quant_attempted, 0) = 0 AND COALESCE(english_attempted, 0) = 0""",
    """UPDATE mock_tests SET test_type = 'sectional', section_subject = 'reasoning'
       WHERE (test_type IS NULL OR test_type = 'full')
       AND COALESCE(reasoning_score, 0) > 0
       AND COALESCE(quant_score, 0) = 0 AND COALESCE(english_score, 0) = 0 AND COALESCE(gk_score, 0) = 0
       AND COALESCE(max_score, 200) <= 50""",
    """UPDATE mock_tests SET test_type = 'sectional', section_subject = 'quant'
       WHERE (test_type IS NULL OR test_type = 'full')
       AND COALESCE(quant_score, 0) > 0
       AND COALESCE(reasoning_score, 0) = 0 AND COALESCE(english_score, 0) = 0 AND COALESCE(gk_score, 0) = 0
       AND COALESCE(max_score, 200) <= 50""",
    """UPDATE mock_tests SET test_type = 'sectional', section_subject = 'english'
       WHERE (test_type IS NULL OR test_type = 'full')
       AND COALESCE(english_score, 0) > 0
       AND COALESCE(reasoning_score, 0) = 0 AND COALESCE(quant_score, 0) = 0 AND COALESCE(gk_score, 0) = 0
       AND COALESCE(max_score, 200) <= 50""",
    """UPDATE mock_tests SET test_type = 'sectional', section_subject = 'gk'
       WHERE (test_type IS NULL OR test_type = 'full')
       AND COALESCE(gk_score, 0) > 0
       AND COALESCE(reasoning_score, 0) = 0 AND COALESCE(quant_score, 0) = 0 AND COALESCE(english_score, 0) = 0
       AND COALESCE(max_score, 200) <= 50""",
    # Performance indexes (safe/idempotent)
    "CREATE INDEX IF NOT EXISTS idx_mock_tests_user_date ON mock_tests (user_id, test_date DESC)",
    "CREATE INDEX IF NOT EXISTS idx_mock_tests_user_type_date ON mock_tests (user_id, test_type, test_date DESC)",
    "CREATE INDEX IF NOT EXISTS idx_calc_attempts_user_created ON calc_question_attempts (user_id, created_at DESC)",
    "CREATE INDEX IF NOT EXISTS idx_calc_attempts_user_type ON calc_question_attempts (user_id, practice_type)",
    "CREATE INDEX IF NOT EXISTS idx_streak_user_type ON streaks (user_id, streak_type)",
    "CREATE INDEX IF NOT EXISTS idx_study_sessions_user_date ON study_sessions (user_id, date DESC)",
    # Notes & mistake journal
    "ALTER TABLE notes ADD COLUMN IF NOT EXISTS note_type VARCHAR(50) DEFAULT 'general'",
    "ALTER TABLE notes ADD COLUMN IF NOT EXISTS tags VARCHAR(500)",
    "ALTER TABLE notes ADD COLUMN IF NOT EXISTS is_mistake BOOLEAN DEFAULT FALSE",
    "ALTER TABLE notes ADD COLUMN IF NOT EXISTS subject VARCHAR(50)",
    "CREATE INDEX IF NOT EXISTS idx_notes_user_updated ON notes (user_id, updated_at DESC)",
    # Revision management extensions
    "ALTER TABLE revision_items ADD COLUMN IF NOT EXISTS notes TEXT",
    "ALTER TABLE revision_items ADD COLUMN IF NOT EXISTS priority VARCHAR(20) DEFAULT 'medium'",
    "ALTER TABLE revision_items ADD COLUMN IF NOT EXISTS difficulty VARCHAR(20) DEFAULT 'medium'",
    "ALTER TABLE revision_items ADD COLUMN IF NOT EXISTS completed_at TIMESTAMPTZ",
    "CREATE INDEX IF NOT EXISTS idx_revision_items_user_due ON revision_items (user_id, next_revision_date)",
    "CREATE INDEX IF NOT EXISTS idx_revision_items_user_priority ON revision_items (user_id, priority)",
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
