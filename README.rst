Ichnaea
=======

Mozilla Ichnaea is an application to provide geo location coordinates
in respond to user requests.


For setup run::

    make
    bin/pserve ichnaea.ini
    Ctrl-C

    <download and unpack cells.txt.gz to data/cells.txt>
    sqlite3 cells.db < import.sql

    bin/pserve ichnaea.ini
    curl "http://localhost:7001/v1/cell?mcc=504&mnc=500&lac=59&cid=2048"
