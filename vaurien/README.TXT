You'll need to get Vaurien from the master branch off of github:

Repo: https://github.com/mozilla-services/vaurien

Mocking out MySQL:

    make chaos_mysql

Mocking out redis:

    make chaos_redis

Notes:
    
* Adding just a 0.01 second delay to mysql causes the test runs to
  go from 6 seconds to 106 seconds on my laptop.
* 

Recovery behaviour:

    * black holes
    * delays
    * dropped connections


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
            * subsequent test runs - ichnaea recovered gracefully
        * With search API
            * no effect. 200 all the time.
        * reproducing this test.
            * doesn't seem reproducible
            * i ran a FLUSHALL on the redis queue, maybe i had some
              stale data or bad queues in redis.  Not sure.
            * ichnaea
    * delay
        * search api:
            * No effect. 200 success everytime.
        * submit api:
            * vaurien yells a lot. Clients properly get 500 errors, and
              system recovers when delay goes away
    * hang connections
        * Search api:
            * No effect. 200 success everytime.
        * submit api:
            * client stalls.
            * Pretty sure that ops has nginx configured to drop
              slow connections, but we need to verify so that we aren't
              open to slowloris attacks



Mysql:

    * failure/blackout
        * with search api
            * 500 errors on blackout, 200 when blackout terminates
        * with submit api
            * 200 success all the time which makes sense, data is just
              queued on redis
    * delay
        * with search api
            * 200 responses come back slowly.  Need to do a load test
            * to see if this opens us up to a slowloris attack.
        * with submit api
            # TODO:
    * hang connections
        * with search api
            # TODO:
        * with submit api
            # TODO:
