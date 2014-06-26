Then start up ichnaea and your vaurien proxies using:

    make start_ichnaea
    make mysql_vaurien
    make redis_vaurien

The vaurien proxies can be instruments to be in one of 3 modes: dummy,
delay or blackout.

    make blackout_mysql
    make blackout_redis

    make delay_mysql
    make delay_redis

    make dummy_mysql
    make dummy_redis

The dummy mode is a plain proxy, delay will delay packets by 1 second,
and blackout will not pass any traffic through to the backend.

Observing the behavior of ichnaea can be done by running:

    make run_submit
    make run_search


----------

Notes:

* Adding just a 0.01 second delay to mysql causes the test runs to
  go from 6 seconds to 106 seconds on my laptop.

Recovery behaviour:

    * black holes
    * delays

Redis:

    * failure/blackout
        * With submit API
            * ichnaea did not recover the first time when tested with
              vaurien.  The server throws these errors:
                    "/Users/victorng/dev/ichnaea/lib/python2.7/site-packages/redis/connection.py",
                    line 334, in send_command
                        self.send_packed_command(self.pack_command(*args))
                      File
                    "/Users/victorng/dev/ichnaea/lib/python2.7/site-packages/redis/connection.py",
                    line 316, in send_packed_command
                        self.connect()
                      File
                    "/Users/victorng/dev/ichnaea/lib/python2.7/site-packages/redis/connection.py",
                    line 253, in connect
                        raise ConnectionError(self._error_message(e))
                    ConnectionError: Error 24 connecting 127.0.0.1:6379. Too many open
                    files.
            * subsequent test runs, i got the expected results -
              client stalls, but ichnaea recovered gracefully when
              goes back to dummy mode
        * With search API
            * no effect. 204 all the time.
        * reproducing this test.
            * doesn't seem reproducible
            * i ran a FLUSHALL on the redis queue, maybe i had some
              stale data or bad queues in redis.  Not sure.
            * ichnaea
    * delay
        * search api:
            * No effect. 204 success everytime.
        * submit api:
            * vaurien yells a lot. Clients properly get 500 errors, and
              system recovers when delay goes away

Mysql:

    * failure/blackout
        * with search api
            * 500 errors on blackout, 204 when blackout terminates
        * with submit api
            * 204 success all the time which makes sense, data is just
              queued on redis
    * delay
        * with search api
            * 204 responses come back slowly.  Need to do a load test
            * to see if this opens us up to a slowloris attack.
        * with submit api
            * no effect 204 responses come back immediately.
