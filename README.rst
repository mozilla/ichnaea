Ichnaea
=======

Mozilla Ichnaea is an application to provide geo location coordinates
in respond to user requests.


For setup run::

    make

    curl http://dump.opencellid.org/cells.txt.gz | gunzip > data/cells.txt
    bin/ichnaea_import ichnaea.ini data/cells.txt

    bin/pserve ichnaea.ini
