"""add practice_visible to problems

Revision ID: b1f4a2c1d8e0
Revises: 298d07770bfb
Create Date: 2026-05-16 14:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "b1f4a2c1d8e0"
down_revision: Union[str, Sequence[str], None] = "298d07770bfb"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "problems",
        sa.Column(
            "practice_visible",
            sa.Boolean(),
            nullable=False,
            server_default=sa.false(),
        ),
    )


def downgrade() -> None:
    op.drop_column("problems", "practice_visible")
