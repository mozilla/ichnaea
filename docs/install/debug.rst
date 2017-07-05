.. _debug:

=========
Debugging
=========

Intro
-----

Once you have a development or production setup of the application,
you might want to test it and see if all the different parts are
configured correctly.


MySQL Config
------------

First, lets check the database configuration. If you have a development
setup, you can open a MySQL client prompt via:

.. code-block:: bash

    docker-compose exec mysql mysql -uroot -plocation location

Otherwise use the the MySQL client tool and connect to your database.

First up, check if the alembic database setup and migration was run:

.. code-block:: sql

    select * from alembic_version;
    +--------------+
    | version_num  |
    +--------------+
    | d2d9ecb12edc |
    +--------------+
    1 row in set (0.00 sec)

This needs to produce a single row and some `version_num` in it.
If it isn't there, check the `Database Setup` part of
:ref:`the deploy docs <deploy>`.

Now check the API keys:

.. code-block:: text

    select * from api_key\G
    *************************** 1. row ***************************
                      valid_key: test
                         maxreq: NULL
                 allow_fallback: 0
                   allow_locate: 1
                 allow_transfer: 0
                      shortname: NULL
                  fallback_name: NULL
                   fallback_url: NULL
             fallback_ratelimit: NULL
    fallback_ratelimit_interval: NULL
          fallback_cache_expire: NULL
            store_sample_locate: 100
            store_sample_submit: 100
    1 row in set (0.00 sec)

And the export config:

.. code-block:: sql

    select * from export_config;
    +----------+-------+----------+------+-----------+--------------+
    | name     | batch | schema   | url  | skip_keys | skip_sources |
    +----------+-------+----------+------+-----------+--------------+
    | internal |   100 | internal | NULL | NULL      | NULL         |
    +----------+-------+----------+------+-----------+--------------+
    1 row in set (0.00 sec)

If you are missing either of these entries, you might have setup your
database as part of a development setup and used the `./server test`
script. This sets up the database for testing needs, but doesn't
configure the export config required for running a real application setup.

One way to correct this is to downgrade and re-upgrade the database
schema using alembic. Using the appropriate docker invocation, you
can run:

.. code-block:: bash

    <...docker or server script...> alembic downgrade base
    <...docker or server script...> alembic upgrade head

This tears down the database schema to an empty state and upgrades it
again. As part of the upgrade, the API key and export config are added.


Connections
-----------

Docker containers typically run on their own IP sub-network and
connecting from inside an application container to a different
machine can be tricky, especially if those other machines are also
docker containers.

Best to check if the containers can actually reach the MySQL database
and Redis datastore.

The easiest way is to follow the instructions in the `Runtime Checks`
part of the :ref:`the deploy docs <deploy>`. Especially calling the
`/__heartbeat__` HTTP endpoint on the web application.

Another way is to start a container and try to connect to the two
external connections from inside it:

.. code-block:: bash

    <...docker or server script...> shell

And inside the container:

.. code-block:: bash

    redis-cli -h $REDIS_HOST
    172.17.0.2:6379> keys *
    1) "_kombu.binding.celery"
    2) "unacked_mutex"
    3) "_kombu.binding.celery.pidbox"

The above output should be there if the async worker containers are
running or have been run once.

In the same way we can connect to the MySQL database from inside the
container. In the same shell container as above:

.. code-block:: bash

    mysql -h $DB_HOST -uroot -plocation location
    ...
    Welcome to the MySQL monitor.  Commands end with ; or \g.
    ...
    mysql>


Async Worker
------------

The async worker uses a Python framework called Celery. You can use the
`Celery monitoring guide <https://celery.readthedocs.io/en/latest/userguide/monitoring.html>`_
for more detailed information.

A basic test is to call the `inspect stats` commands. Open a shell container
and inside it run:

.. code-block:: bash

    /app/bin/celery -A ichnaea.async.app:celery_app inspect stats
    -> celery@388ec81273ba: OK
    {
        ...
        "total": {
            "ichnaea.data.tasks.monitor_api_key_limits": 1,
            "ichnaea.data.tasks.monitor_api_users": 1,
            "ichnaea.data.tasks.monitor_queue_size": 15,
            "ichnaea.data.tasks.update_blue": 304,
            "ichnaea.data.tasks.update_cell": 66,
            "ichnaea.data.tasks.update_cellarea": 21,
            "ichnaea.data.tasks.update_incoming": 29,
            "ichnaea.data.tasks.update_wifi": 368
        }
    }

The output is pretty long. For us the `total` section is the most
interesting. If you have your worker and scheduler container running
for some minutes, this section should fill up with various tasks.

If this section continues to be empty, something is wrong with the
scheduler and it isn't adding tasks to the worker queues.


Data Pipeline
-------------

Now that all the building blocks are in place, let's try to send them
real data to the service and see how it processes it.

Assuming containers for all three roles are running, we'll use the HTTP
geosubmit v2 API endpoint to send some new data to the service:

.. code-block:: bash

    curl -H 'Content-Type: application/json' http://127.0.0.1:8000/v2/geosubmit?key=test -d \
    '{"items": [{"wifiAccessPoints": [{"macAddress": "94B40F010D01"}, {"macAddress": "94B40F010D00"}, {"macAddress": "94B40F010D03"}], "position": {"latitude": 51.0, "longitude": 10.0}}]}'

We can find this data again in Redis, open a Redis client and do:

.. code-block:: bash

    lrange "queue_export_internal" 0 10
    1) "{\"api_key\": \"test\", \"report\": {\"timestamp\": 1499267286717, \"bluetoothBeacons\": [], \"wifiAccessPoints\": [{\"macAddress\": \"94B40F010D01\"}, {\"macAddress\": \"94B40F010D00\"}, {\"macAddress\": \"94B40F010D03\"}], \"cellTowers\": [], \"position\": {\"latitude\": 51.0, \"longitude\": 10.0}}}"

The data pipeline is optimized for production use and processes data in
batches or if data sits too long in a queue. We can use the later feature
to trick the pipeline into processing data sooner.

In the same Redis client use:

.. code-block:: bash

    expire "queue_export_internal" 300

This tells the queue to get deleted in 300 seconds. The scheduler runs
a task to check this queue about once per minute and checks both its
length and its remaining time-to-live.

If we check the available Redis keys again, we might see something like:

.. code-block:: bash

    keys *
    1) "_kombu.binding.celery"
    2) "apiuser:submit:test:2017-07-05"
    3) "update_wifi_0"
    4) "unacked_mutex"
    5) "statcounter_unique_wifi_20170705"
    6) "_kombu.binding.celery.pidbox"

If we wait a bit longer, the `update_wifi_0` entry should vanish.

Once that happened, we can check the database directly. On a MySQL
client prompt do:

.. code-block:: sql

    select hex(`mac`), lat, lon from wifi_shard_0;
    +--------------+------+------+
    | hex(`mac`)   | lat  | lon  |
    +--------------+------+------+
    | 94B40F010D00 |   51 |   10 |
    | 94B40F010D01 |   51 |   10 |
    | 94B40F010D03 |   51 |   10 |
    +--------------+------+------+
    3 rows in set (0.00 sec)

Once the data has been processed, we can try the public HTTP API again
and see if we can locate us. To do that we can use both the geolocate
and region APIs:

.. code-block:: bash

    curl -H 'Content-Type: application/json' http://127.0.0.1:8000/v1/geolocate?key=test -d \
    '{"wifiAccessPoints": [{"macAddress": "94B40F010D01"}, {"macAddress": "94B40F010D00"}, {"macAddress": "94B40F010D03"}]}'

This should produce a response:

.. code-block:: javascript

    {"location": {"lat": 51.0, "lng": 10.0}, "accuracy": 10.0}

And again using the region API:

.. code-block:: bash

    curl -H 'Content-Type: application/json' http://127.0.0.1:8000/v1/country?key=test -d \
    '{"wifiAccessPoints": [{"macAddress": "94B40F010D01"}, {"macAddress": "94B40F010D00"}, {"macAddress": "94B40F010D03"}]}'

.. code-block:: javascript

    {"country_code": "DE", "country_name": "Germany"}

If you check Redis queues again, there's a new entry in there for the
geolocate query we just submitted:

.. code-block:: bash

    lrange "queue_export_internal" 0 10
    1) "{\"api_key\": \"test\", \"report\": {\"wifiAccessPoints\": [{\"macAddress\": \"94b40f010d01\"}, {\"macAddress\": \"94b40f010d00\"}, {\"macAddress\": \"94b40f010d03\"}], \"fallbacks\": {\"ipf\": true, \"lacf\": true}, \"position\": {\"latitude\": 51.0, \"longitude\": 10.0, \"accuracy\": 10.0, \"source\": \"query\"}}}"

Note the ``"source": "query"`` part at the end, which tells the pipeline
the position data does not represent a GPS verified position, but was
the result of a query.

You can use the same `expire` trick as above again, to get the data
processed faster.

On a MySQL prompt, you can see the result:

.. code-block:: sql

    select hex(`mac`), last_seen from wifi_shard_0;
    +--------------+------------+
    | hex(`mac`)   | last_seen  |
    +--------------+------------+
    | 94B40F010D00 | 2017-07-05 |
    | 94B40F010D01 | 2017-07-05 |
    | 94B40F010D03 | 2017-07-05 |
    +--------------+------------+
    3 rows in set (0.00 sec)

Since all the WiFi networks were already known, their position just got
confirmed. This gets stored in the `last_seen` column, which tracks when
the network was last confirmed in a query.
