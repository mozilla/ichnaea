Ichnaea
=======

Mozilla Ichnaea is an application to provide geo location coordinates
in respond to user requests.


For setup run::

    make
    bin/pserve ichnaea.ini
    Ctrl-C

    <download and unpack http://dump.opencellid.org/cells.txt.gz to data/cells.txt>
    sqlite3 cells.db < import.sql

    bin/pserve ichnaea.ini
    curl http://localhost:7001/v1/cell/724/5/31421/60420242
