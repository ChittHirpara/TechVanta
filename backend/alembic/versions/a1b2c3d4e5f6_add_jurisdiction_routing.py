"""add_jurisdiction_routing

Revision ID: a1b2c3d4e5f6
Revises: 7a9f257d81a2
Create Date: 2026-09-10 23:30:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'a1b2c3d4e5f6'
down_revision: Union[str, None] = '7a9f257d81a2'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Create verifier_jurisdictions table
    op.create_table(
        'verifier_jurisdictions',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('district', sa.String(length=150), nullable=False),
        sa.Column('tehsil', sa.String(length=150), nullable=True),
        sa.Column('village', sa.String(length=150), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_verifier_jurisdictions_user_id'), 'verifier_jurisdictions', ['user_id'], unique=False)
    op.create_index(op.f('ix_verifier_jurisdictions_district'), 'verifier_jurisdictions', ['district'], unique=False)
    op.create_index(op.f('ix_verifier_jurisdictions_tehsil'), 'verifier_jurisdictions', ['tehsil'], unique=False)
    op.create_index(op.f('ix_verifier_jurisdictions_village'), 'verifier_jurisdictions', ['village'], unique=False)

    # 2. Add additive columns to documents table (with batch mode for SQLite compatibility)
    with op.batch_alter_table('documents') as batch_op:
        batch_op.add_column(sa.Column('assigned_verifier_id', sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column('claimed_at', sa.DateTime(timezone=True), nullable=True))
        batch_op.add_column(sa.Column('is_escalated', sa.Boolean(), server_default='0', nullable=False))
        batch_op.add_column(sa.Column('escalation_reason', sa.String(length=255), nullable=True))
        batch_op.create_foreign_key('fk_documents_assigned_verifier', 'users', ['assigned_verifier_id'], ['id'], ondelete='SET NULL')
        batch_op.create_index(batch_op.f('ix_documents_assigned_verifier_id'), ['assigned_verifier_id'], unique=False)


def downgrade() -> None:
    with op.batch_alter_table('documents') as batch_op:
        batch_op.drop_index(batch_op.f('ix_documents_assigned_verifier_id'))
        batch_op.drop_constraint('fk_documents_assigned_verifier', type_='foreignkey')
        batch_op.drop_column('escalation_reason')
        batch_op.drop_column('is_escalated')
        batch_op.drop_column('claimed_at')
        batch_op.drop_column('assigned_verifier_id')

    op.drop_index(op.f('ix_verifier_jurisdictions_village'), table_name='verifier_jurisdictions')
    op.drop_index(op.f('ix_verifier_jurisdictions_tehsil'), table_name='verifier_jurisdictions')
    op.drop_index(op.f('ix_verifier_jurisdictions_district'), table_name='verifier_jurisdictions')
    op.drop_index(op.f('ix_verifier_jurisdictions_user_id'), table_name='verifier_jurisdictions')
    op.drop_table('verifier_jurisdictions')
