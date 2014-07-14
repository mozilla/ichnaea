Running the vaurien tests

You need to have mysql_vaurien, redis_vaurien and ichnaea itself
running.

From the top level ichnaea directory:

make mysql_vaurien
make redis_vaurien
make start_ichnaea

Now run the tests:

make automate_vaurien
