#!/bin/bash

VOLUME_HOME="/var/lib/mysql"

if [[ ! -d $VOLUME_HOME/mysql ]]; then
    echo "=> An empty or uninitialized MySQL volume is detected in $VOLUME_HOME"
    echo "=> Installing MySQL ..."
    /bin/bash /setup.sh
else
    echo "=> Using an existing volume of MySQL"
fi

echo "=> Starting mysql"
exec /entrypoint.sh mysqld
