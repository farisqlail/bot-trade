"""initial schema

Revision ID: 001
Revises:
Create Date: 2026-01-01 00:00:00.000000
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = '001'
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        'users',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('email', sa.String(255), nullable=False),
        sa.Column('username', sa.String(100), nullable=False),
        sa.Column('hashed_password', sa.String(255), nullable=False),
        sa.Column('is_active', sa.Boolean(), nullable=True, default=True),
        sa.Column('is_superuser', sa.Boolean(), nullable=True, default=False),
        sa.Column('failed_login_attempts', sa.Integer(), nullable=True, default=0),
        sa.Column('locked_until', sa.DateTime(timezone=True), nullable=True),
        sa.Column('last_login', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_users_email', 'users', ['email'], unique=True)
    op.create_index('ix_users_username', 'users', ['username'], unique=True)

    op.create_table(
        'settings',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('symbol', sa.String(255), nullable=True, default='featured'),
        sa.Column('leverage', sa.Integer(), nullable=True, default=10),
        sa.Column('risk_percent', sa.Float(), nullable=True, default=1.0),
        sa.Column('max_open_trades', sa.Integer(), nullable=True, default=5),
        sa.Column('default_stop_loss', sa.Float(), nullable=True, default=103500.0),
        sa.Column('default_take_profit', sa.Float(), nullable=True, default=107000.0),
        sa.Column('daily_loss_limit_percent', sa.Float(), nullable=True, default=3.0),
        sa.Column('max_drawdown_percent', sa.Float(), nullable=True, default=10.0),
        sa.Column('consecutive_loss_limit', sa.Integer(), nullable=True, default=3),
        sa.Column('bot_enabled', sa.Boolean(), nullable=True, default=False),
        sa.Column('auto_trade', sa.Boolean(), nullable=True, default=False),
        sa.Column('ai_analysis_enabled', sa.Boolean(), nullable=True, default=True),
        sa.Column('ai_analysis_interval', sa.Integer(), nullable=True, default=300),
        sa.Column('binance_api_key', sa.String(255), nullable=True),
        sa.Column('binance_api_secret', sa.String(255), nullable=True),
        sa.Column('use_testnet', sa.Boolean(), nullable=True, default=True),
        sa.Column('notification_settings', postgresql.JSON(astext_type=sa.Text()), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(['user_id'], ['users.id']),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('user_id'),
    )

    op.create_table(
        'signals',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('symbol', sa.String(255), nullable=False),
        sa.Column('signal_type', sa.String(10), nullable=False),
        sa.Column('source', sa.String(20), nullable=True),
        sa.Column('price_at_signal', sa.Float(), nullable=False),
        sa.Column('suggested_entry', sa.Float(), nullable=True),
        sa.Column('suggested_sl', sa.Float(), nullable=True),
        sa.Column('suggested_tp', sa.Float(), nullable=True),
        sa.Column('confidence', sa.Float(), nullable=True),
        sa.Column('reasoning', sa.Text(), nullable=True),
        sa.Column('indicators', sa.Text(), nullable=True),
        sa.Column('is_executed', sa.Boolean(), nullable=True, default=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column('expires_at', sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_signals_symbol', 'signals', ['symbol'])

    op.create_table(
        'trades',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('exchange_order_id', sa.String(100), nullable=True),
        sa.Column('symbol', sa.String(255), nullable=False),
        sa.Column('direction', sa.String(10), nullable=False),
        sa.Column('status', sa.String(20), nullable=True, default='PENDING'),
        sa.Column('entry_price', sa.Float(), nullable=False),
        sa.Column('stop_loss', sa.Float(), nullable=False),
        sa.Column('take_profit', sa.Float(), nullable=False),
        sa.Column('exit_price', sa.Float(), nullable=True),
        sa.Column('quantity', sa.Float(), nullable=False),
        sa.Column('leverage', sa.Integer(), nullable=True, default=10),
        sa.Column('risk_amount', sa.Float(), nullable=False),
        sa.Column('risk_percent', sa.Float(), nullable=False),
        sa.Column('pnl', sa.Float(), nullable=True),
        sa.Column('pnl_percent', sa.Float(), nullable=True),
        sa.Column('fees', sa.Float(), nullable=True, default=0.0),
        sa.Column('signal_id', sa.Integer(), nullable=True),
        sa.Column('notes', sa.Text(), nullable=True),
        sa.Column('opened_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('closed_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(['user_id'], ['users.id']),
        sa.ForeignKeyConstraint(['signal_id'], ['signals.id']),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_trades_user_id', 'trades', ['user_id'])
    op.create_index('ix_trades_symbol', 'trades', ['symbol'])
    op.create_index('ix_trades_status', 'trades', ['status'])

    op.create_table(
        'ai_analysis',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('symbol', sa.String(255), nullable=False),
        sa.Column('model_name', sa.String(100), nullable=False),
        sa.Column('trend', sa.String(20), nullable=True),
        sa.Column('sentiment', sa.String(20), nullable=True),
        sa.Column('confidence', sa.Float(), nullable=True),
        sa.Column('support_levels', postgresql.JSON(astext_type=sa.Text()), nullable=True),
        sa.Column('resistance_levels', postgresql.JSON(astext_type=sa.Text()), nullable=True),
        sa.Column('key_levels', postgresql.JSON(astext_type=sa.Text()), nullable=True),
        sa.Column('analysis_text', sa.Text(), nullable=False),
        sa.Column('raw_response', sa.Text(), nullable=True),
        sa.Column('market_data_snapshot', postgresql.JSON(astext_type=sa.Text()), nullable=True),
        sa.Column('price_at_analysis', sa.Float(), nullable=True),
        sa.Column('recommended_action', sa.String(20), nullable=True),
        sa.Column('suggested_entry', sa.Float(), nullable=True),
        sa.Column('suggested_sl', sa.Float(), nullable=True),
        sa.Column('suggested_tp', sa.Float(), nullable=True),
        sa.Column('processing_time_ms', sa.Integer(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_ai_analysis_symbol', 'ai_analysis', ['symbol'])

    op.create_table(
        'risk_events',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('event_type', sa.String(50), nullable=False),
        sa.Column('severity', sa.String(20), nullable=False),
        sa.Column('title', sa.String(200), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('triggered_value', sa.Float(), nullable=True),
        sa.Column('threshold_value', sa.Float(), nullable=True),
        sa.Column('action_taken', sa.String(200), nullable=True),
        sa.Column('event_metadata', postgresql.JSON(astext_type=sa.Text()), nullable=True),
        sa.Column('is_resolved', sa.Integer(), nullable=True, default=0),
        sa.Column('resolved_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.ForeignKeyConstraint(['user_id'], ['users.id']),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_risk_events_user_id', 'risk_events', ['user_id'])


def downgrade() -> None:
    op.drop_table('risk_events')
    op.drop_table('ai_analysis')
    op.drop_table('trades')
    op.drop_table('signals')
    op.drop_table('settings')
    op.drop_table('users')
