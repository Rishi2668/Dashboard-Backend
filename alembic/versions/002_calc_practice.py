"""calc practice tables

Revision ID: 002
Revises: 001
"""

from alembic import op

revision = "002"
down_revision = "001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
        CREATE TABLE IF NOT EXISTS calc_practice_sessions (
            id SERIAL PRIMARY KEY,
            user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            mode VARCHAR(30) NOT NULL,
            difficulty VARCHAR(20) DEFAULT 'medium',
            practice_types TEXT DEFAULT '["mixed"]',
            started_at TIMESTAMPTZ DEFAULT NOW(),
            ended_at TIMESTAMPTZ,
            duration_limit_sec INTEGER,
            total_questions INTEGER DEFAULT 0,
            correct_count INTEGER DEFAULT 0,
            skipped_count INTEGER DEFAULT 0,
            total_time_ms INTEGER DEFAULT 0,
            fastest_time_ms INTEGER,
            xp_earned INTEGER DEFAULT 0,
            completed BOOLEAN DEFAULT FALSE
        );
        CREATE INDEX IF NOT EXISTS ix_calc_practice_sessions_user_id ON calc_practice_sessions(user_id);

        CREATE TABLE IF NOT EXISTS calc_question_attempts (
            id SERIAL PRIMARY KEY,
            session_id INTEGER NOT NULL REFERENCES calc_practice_sessions(id) ON DELETE CASCADE,
            user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            practice_type VARCHAR(50) NOT NULL,
            difficulty VARCHAR(20) NOT NULL,
            question_text TEXT NOT NULL,
            correct_answer DOUBLE PRECISION NOT NULL,
            user_answer DOUBLE PRECISION,
            is_correct BOOLEAN DEFAULT FALSE,
            skipped BOOLEAN DEFAULT FALSE,
            time_ms INTEGER DEFAULT 0,
            fingerprint VARCHAR(64) NOT NULL,
            explanation TEXT DEFAULT '',
            created_at TIMESTAMPTZ DEFAULT NOW()
        );
        CREATE INDEX IF NOT EXISTS ix_calc_question_attempts_user_id ON calc_question_attempts(user_id);
        CREATE INDEX IF NOT EXISTS ix_calc_question_attempts_session_id ON calc_question_attempts(session_id);

        CREATE TABLE IF NOT EXISTS calc_pending_questions (
            question_id VARCHAR(36) PRIMARY KEY,
            user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            practice_type VARCHAR(50) NOT NULL,
            difficulty VARCHAR(20) NOT NULL,
            question_text TEXT NOT NULL,
            correct_answer DOUBLE PRECISION NOT NULL,
            answer_tolerance DOUBLE PRECISION DEFAULT 0.01,
            explanation TEXT DEFAULT '',
            fingerprint VARCHAR(64) NOT NULL,
            created_at TIMESTAMPTZ DEFAULT NOW()
        );

        CREATE TABLE IF NOT EXISTS calc_weak_area_stats (
            id SERIAL PRIMARY KEY,
            user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            practice_type VARCHAR(50) NOT NULL,
            total_attempts INTEGER DEFAULT 0,
            correct_count INTEGER DEFAULT 0,
            total_time_ms INTEGER DEFAULT 0,
            fastest_time_ms INTEGER,
            updated_at TIMESTAMPTZ DEFAULT NOW()
        );
        CREATE INDEX IF NOT EXISTS ix_calc_weak_area_stats_user_id ON calc_weak_area_stats(user_id);
    """)


def downgrade() -> None:
    op.execute("""
        DROP TABLE IF EXISTS calc_weak_area_stats;
        DROP TABLE IF EXISTS calc_pending_questions;
        DROP TABLE IF EXISTS calc_question_attempts;
        DROP TABLE IF EXISTS calc_practice_sessions;
    """)
