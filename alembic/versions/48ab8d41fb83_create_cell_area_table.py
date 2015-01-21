"""create cell area table

Revision ID: 48ab8d41fb83
Revises: 462e75b30b74
Create Date: 2014-11-24 05:14:52.859389

"""

# revision identifiers, used by Alembic.
revision = '48ab8d41fb83'
down_revision = '462e75b30b74'

from alembic import op
import sqlalchemy as sa


def upgrade():
    # Create new table
    op.create_table(
        'cell_area',
        sa.Column('created', sa.DateTime),
        sa.Column('modified', sa.DateTime),
        sa.Column('lat', sa.dialects.mysql.DOUBLE(asdecimal=False)),
        sa.Column('lon', sa.dialects.mysql.DOUBLE(asdecimal=False)),
        sa.Column('radio', sa.dialects.mysql.TINYINT,
                  autoincrement=False, primary_key=True),
        sa.Column('mcc', sa.dialects.mysql.SMALLINT,
                  autoincrement=False, primary_key=True),
        sa.Column('mnc', sa.dialects.mysql.SMALLINT,
                  autoincrement=False, primary_key=True),
        sa.Column('lac', sa.dialects.mysql.SMALLINT(unsigned=True),
                  autoincrement=False, primary_key=True),
        sa.Column('range', sa.dialects.mysql.INTEGER),
        sa.Column('avg_cell_range', sa.dialects.mysql.INTEGER),
        sa.Column('num_cells', sa.dialects.mysql.INTEGER(unsigned=True)),
        mysql_engine='InnoDB',
        mysql_charset='utf8',
    )

    # Add a migration to copy over all area records from the cell table
    # to the new cell_area table
    op.execute("""
        INSERT INTO
            cell_area
            (
                `created`,
                `modified`,
                `lat`,
                `lon`,
                `radio`,
                `mcc`,
                `mnc`,
                `lac`,
                `range`
            )
        SELECT
            `created`,
            `modified`,
            `lat`,
            `lon`,
            `radio`,
            `mcc`,
            `mnc`,
            `lac`,
            `range`
        FROM
            cell CELL
        WHERE
            cid = -2
    """)

    # Set the num_cells field to the number of cell towers in that area
    op.execute("""
        UPDATE
            cell_area CELL_AREA
        SET
            num_cells = (
                SELECT
                    count(*)
                FROM
                    cell CELL_ALL
                WHERE
                    CELL_AREA.radio = CELL_ALL.radio AND
                    CELL_AREA.mcc = CELL_ALL.mcc AND
                    CELL_AREA.mnc = CELL_ALL.mnc AND
                    CELL_AREA.lac = CELL_ALL.lac
            )
    """)

    # Set the avg_cell_range to the average range of the cells in that area
    op.execute("""
        UPDATE
            cell_area CELL_AREA
        SET
            avg_cell_range = (
                SELECT
                    AVG(`range`)
                FROM
                    cell CELL_ALL
                WHERE
                    CELL_AREA.radio = CELL_ALL.radio AND
                    CELL_AREA.mcc = CELL_ALL.mcc AND
                    CELL_AREA.mnc = CELL_ALL.mnc AND
                    CELL_AREA.lac = CELL_ALL.lac
            )
    """)

    # Remove the existing LACs from the Cell table
    op.execute('DELETE FROM cell WHERE cid=-2')


def downgrade():
    op.drop_table('cell_area')
