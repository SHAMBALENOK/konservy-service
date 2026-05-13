"""Initial schema - accounts and transactions

Revision ID: 001
Revises: 
Create Date: 2024-01-01 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '001'
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create initial database schema."""
    
    # Create accounts table
    op.create_table(
        'accounts',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('account_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('user_id', sa.String(length=255), nullable=False),
        sa.Column('account_number', sa.String(length=20), nullable=False),
        sa.Column('currency', sa.String(length=3), nullable=False, default='USD'),
        sa.Column('balance', sa.Numeric(precision=19, scale=2), nullable=False, default=0.00),
        sa.Column('is_active', sa.Boolean(), nullable=False, default=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_accounts_account_id'), 'accounts', ['account_id'], unique=True)
    op.create_index(op.f('ix_accounts_user_id'), 'accounts', ['user_id'], unique=True)
    op.create_index(op.f('ix_accounts_account_number'), 'accounts', ['account_number'], unique=True)
    
    # Create transactions table
    op.create_table(
        'transactions',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('transaction_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('idempotency_key', sa.String(length=255), nullable=True),
        sa.Column('type', sa.Enum('TRANSFER', 'DEPOSIT', 'WITHDRAWAL', 'REFUND', name='transactiontype'), nullable=False),
        sa.Column('amount', sa.Numeric(precision=19, scale=2), nullable=False),
        sa.Column('currency', sa.String(length=3), nullable=False, default='USD'),
        sa.Column('source_account_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('destination_account_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('status', sa.Enum('PENDING', 'COMPLETED', 'FAILED', 'CANCELLED', name='transactionstatus'), nullable=False, default='pending'),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('reference', sa.String(length=255), nullable=True),
        sa.Column('failure_reason', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('processed_at', sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['source_account_id'], ['accounts.account_id'], ),
        sa.ForeignKeyConstraint(['destination_account_id'], ['accounts.account_id'], ),
    )
    op.create_index(op.f('ix_transactions_transaction_id'), 'transactions', ['transaction_id'], unique=True)
    op.create_index(op.f('ix_transactions_idempotency_key'), 'transactions', ['idempotency_key'], unique=True)
    op.create_index(op.f('ix_transactions_source_account_id'), 'transactions', ['source_account_id'])
    op.create_index(op.f('ix_transactions_destination_account_id'), 'transactions', ['destination_account_id'])
    op.create_index(op.f('ix_transactions_created_at'), 'transactions', ['created_at'])


def downgrade() -> None:
    """Drop initial database schema."""
    op.drop_index(op.f('ix_transactions_created_at'), table_name='transactions')
    op.drop_index(op.f('ix_transactions_destination_account_id'), table_name='transactions')
    op.drop_index(op.f('ix_transactions_source_account_id'), table_name='transactions')
    op.drop_index(op.f('ix_transactions_idempotency_key'), table_name='transactions')
    op.drop_index(op.f('ix_transactions_transaction_id'), table_name='transactions')
    op.drop_table('transactions')
    
    op.drop_index(op.f('ix_accounts_account_number'), table_name='accounts')
    op.drop_index(op.f('ix_accounts_user_id'), table_name='accounts')
    op.drop_index(op.f('ix_accounts_account_id'), table_name='accounts')
    op.drop_table('accounts')
    
    # Drop enums
    op.execute('DROP TYPE IF EXISTS transactionstatus')
    op.execute('DROP TYPE IF EXISTS transactiontype')
