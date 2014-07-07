"""floating point coords

Revision ID: 2f26a4df27af
Revises: 1ac6c3d2ccc4
Create Date: 2014-07-07 10:47:09.197841

"""

# revision identifiers, used by Alembic.
revision = '2f26a4df27af'
down_revision = '1ac6c3d2ccc4'

from alembic import op
import sqlalchemy as sa


table_cols = [("cell", ["lat", "max_lat", "min_lat",
                        "lon", "max_lon", "min_lon"]),
              ("wifi", ["lat", "max_lat", "min_lat",
                        "lon", "max_lon", "min_lon"]),
              ("cell_measure", ["lat", "lon"]),
              ("wifi_measure", ["lat", "lon"])]


def upgrade():

    for (table, cols) in table_cols:

        # First, rename all existing columns from foo to foo_int and add
        # double columns called foo.
        clauses = [str.format("CHANGE COLUMN {col} {col}_int INTEGER(11), " +
                              "ADD COLUMN {col} DOUBLE AFTER {col}_int",
                              col=col)
                   for col in cols]
        stmt = str.format("ALTER TABLE {table} {clauses}",
                          table=table, clauses=", ".join(clauses))
        op.execute(stmt)

        # Next, update all the foo columns to the scaled value of the foo_int
        # columns.
        clauses = [str.format("{col} = {col}_int * 0.0000001", col=col)
                   for col in cols]
        stmt = str.format("UPDATE {table} SET {clauses}",
                          table=table, clauses=", ".join(clauses))
        op.execute(stmt)

        # Next, drop the foo_int columns.
        clauses = [str.format("DROP COLUMN {col}_int", col=col)
                   for col in cols]
        stmt = str.format("ALTER TABLE {table} {clauses}",
                          table=table, clauses=", ".join(clauses))
        op.execute(stmt)

        # Finally, optimize the table.
        op.execute("OPTIMIZE TABLE " + table)


def downgrade():
    for (table, cols) in table_cols:

        # First, rename all existing columns from foo to foo_double and add
        # integer(11) columns called foo.
        clauses = [str.format("CHANGE COLUMN {col} {col}_double DOUBLE, " +
                              "ADD COLUMN {col} INTEGER(11) AFTER {col}_int",
                              col=col)
                   for col in cols]
        stmt = str.format("ALTER TABLE {table} {clauses}",
                          table=table, clauses=", ".join(clauses))
        op.execute(stmt)

        # Next, update all the foo columns to the scaled value of the
        # foo_double columns.
        clauses = [str.format("{col} = {col}_double * 10000000", col=col)
                   for col in cols]
        stmt = str.format("UPDATE {table} SET {clauses}",
                          table=table, clauses=", ".join(clauses))
        op.execute(stmt)

        # Next, drop the foo_double columns.
        clauses = [str.format("DROP COLUMN {col}_double", col=col)
                   for col in cols]
        stmt = str.format("ALTER TABLE {table} {clauses}",
                          table=table, clauses=", ".join(clauses))
        op.execute(stmt)

        # Finally, optimize the table.
        op.execute("OPTIMIZE TABLE " + table)
