#!/bin/sh

# a simple script to generate the DDL between the current alembic
# revision and alembic head

cur_rev=`bin/alembic current 2>&1 | grep "^Current"|sed -e "s/.*-> \([0-9a-z]*\),.*/\1/"`
head_rev=`bin/alembic history|head -n 5|grep "^Rev:"|sed -e "s/.* \([0-9a-z]*\) .*/\1/"`
cmd="bin/alembic upgrade "$cur_rev":"$head_rev" --sql"
echo $cmd
exec $cmd
