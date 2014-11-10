"""update cell towers with wrong radio types

Revision ID: 48f67ea76ef7
Revises: 4c7e55213558
Create Date: 2014-11-10 23:13:16.333794

"""

# revision identifiers, used by Alembic.
revision = '48f67ea76ef7'
down_revision = '4c7e55213558'

from alembic import op


def upgrade():
    # Create any missing lac area cells
    op.execute("""
        INSERT INTO
          cell (
            radio,
            mcc,
            mnc,
            lac,
            cid,
            new_measures,
            total_measures,
            created,
            modified
          )
        SELECT DISTINCT
          CELL_ALL.radio,
          CELL_ALL.mcc,
          CELL_ALL.mnc,
          CELL_ALL.lac,
          -2,
          1,
          0,
          NOW(),
          NOW()
        FROM
          cell CELL_ALL
        WHERE
          NOT EXISTS (
            SELECT
              *
            FROM
              cell CELL_AREA
            WHERE
              CELL_AREA.radio = CELL_ALL.radio AND
              CELL_AREA.mcc = CELL_ALL.mcc AND
              CELL_AREA.mnc = CELL_ALL.mnc AND
              CELL_AREA.lac = CELL_ALL.lac AND
              CELL_AREA.cid = -2
          );
    """)

    # Mark all affected areas for recomputation
    op.execute("""
        UPDATE
          cell CELL_AREA, cell CELL_BAD
        SET
          CELL_AREA.new_measures = 1
        WHERE
          CELL_BAD.radio = 0 AND
          CELL_BAD.cid > 65535 AND
          CELL_BAD.mnc=CELL_AREA.mnc AND
          CELL_BAD.mcc=CELL_AREA.mcc AND
          CELL_BAD.lac=CELL_AREA.lac AND
          CELL_AREA.cid = -2 AND
          (
            CELL_AREA.radio = 0 OR
            CELL_AREA.radio = 2
          );
    """)

    # Remove the invalid cells which collide with existing cells
    op.execute("""
        DELETE
          CELL_BAD
        FROM
          cell CELL_ALL, cell CELL_BAD
        WHERE
          CELL_BAD.cid > 65535 AND
          CELL_BAD.radio = 0 AND
          CELL_BAD.mcc = CELL_ALL.mcc AND
          CELL_BAD.mnc = CELL_ALL.mnc AND
          CELL_BAD.cid = CELL_ALL.cid AND
          CELL_BAD.lac = CELL_ALL.lac AND
          CELL_ALL.radio = 2;
    """)

    # Correct the remaining cells to be UMTS
    op.execute("""
        UPDATE
          cell
        SET
          radio = 2
        WHERE
          cid > 65535 AND
          radio = 0;
    """)


def downgrade():
    pass
