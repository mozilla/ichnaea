"""create ocid cell area table

Revision ID: 1a116bcd0851
Revises: 48ab8d41fb83
Create Date: 2014-12-09 21:57:57.514513

"""

# revision identifiers, used by Alembic.
revision = '1a116bcd0851'
down_revision = '48ab8d41fb83'

from alembic import op
import sqlalchemy as sa


def upgrade():
    # Create new table
    op.create_table(
        'ocid_cell_area',
        sa.Column('created', sa.DateTime),
        sa.Column('modified', sa.DateTime),
        sa.Column('lat', sa.dialects.mysql.DOUBLE(asdecimal=False)),
        sa.Column('lon', sa.dialects.mysql.DOUBLE(asdecimal=False)),
        sa.Column('radio', sa.dialects.mysql.TINYINT, autoincrement=False, primary_key=True),
        sa.Column('mcc', sa.dialects.mysql.SMALLINT, autoincrement=False, primary_key=True),
        sa.Column('mnc', sa.dialects.mysql.SMALLINT, autoincrement=False, primary_key=True),
        sa.Column('lac', sa.dialects.mysql.SMALLINT(unsigned=True), autoincrement=False, primary_key=True),
        sa.Column('range', sa.dialects.mysql.INTEGER),
        sa.Column('avg_cell_range', sa.dialects.mysql.INTEGER),
        sa.Column('num_cells', sa.dialects.mysql.INTEGER(unsigned=True)),
        mysql_engine='InnoDB',
        mysql_charset='utf8',
    )


def downgrade():
    op.drop_table('ocid_cell_area')
