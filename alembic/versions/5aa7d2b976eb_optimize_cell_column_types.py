"""Optimize cell column types

Revision ID: 5aa7d2b976eb
Revises: 4508f02e6cd7
Create Date: 2014-08-18 16:40:37.646844

"""

# revision identifiers, used by Alembic.
revision = '5aa7d2b976eb'
down_revision = '4508f02e6cd7'

from alembic import op
import sqlalchemy as sa


def upgrade():
    mnc_stmt = "CHANGE COLUMN mnc mnc SMALLINT"
    psc_stmt = "CHANGE COLUMN psc psc SMALLINT"
    radio_stmt = "CHANGE COLUMN radio radio TINYINT"
    ta_stmt = "CHANGE COLUMN ta ta TINYINT"

    op.execute(sa.text("ALTER TABLE cell " +
                       ", ".join([radio_stmt, mnc_stmt, psc_stmt])))

    op.execute(sa.text("ALTER TABLE cell_blacklist " +
                       ", ".join([radio_stmt, mnc_stmt])))

    op.execute(sa.text("ALTER TABLE cell_measure " +
                       ", ".join([radio_stmt, mnc_stmt, psc_stmt, ta_stmt])))


def downgrade():
    mnc_stmt = "CHANGE COLUMN mnc mnc INTEGER"
    psc_stmt = "CHANGE COLUMN psc psc INTEGER"
    radio_stmt = "CHANGE COLUMN radio radio SMALLINT"
    ta_stmt = "CHANGE COLUMN ta ta SMALLINT"

    op.execute(sa.text("ALTER TABLE cell " +
                       ", ".join([radio_stmt, mnc_stmt, psc_stmt])))

    op.execute(sa.text("ALTER TABLE cell_blacklist " +
                       ", ".join([radio_stmt, mnc_stmt])))

    op.execute(sa.text("ALTER TABLE cell_measure " +
                       ", ".join([radio_stmt, mnc_stmt, psc_stmt, ta_stmt])))
