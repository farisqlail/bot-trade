"""widen symbol columns for polymarket slugs

Revision ID: 002
Revises: 001
Create Date: 2026-05-24 00:00:00.000000
"""
from alembic import op
import sqlalchemy as sa


revision = "002"
down_revision = "001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.alter_column("settings", "symbol", existing_type=sa.String(length=20), type_=sa.String(length=255))
    op.alter_column("signals", "symbol", existing_type=sa.String(length=20), type_=sa.String(length=255))
    op.alter_column("trades", "symbol", existing_type=sa.String(length=20), type_=sa.String(length=255))
    op.alter_column("ai_analysis", "symbol", existing_type=sa.String(length=20), type_=sa.String(length=255))


def downgrade() -> None:
    op.alter_column("ai_analysis", "symbol", existing_type=sa.String(length=255), type_=sa.String(length=20))
    op.alter_column("trades", "symbol", existing_type=sa.String(length=255), type_=sa.String(length=20))
    op.alter_column("signals", "symbol", existing_type=sa.String(length=255), type_=sa.String(length=20))
    op.alter_column("settings", "symbol", existing_type=sa.String(length=255), type_=sa.String(length=20))
