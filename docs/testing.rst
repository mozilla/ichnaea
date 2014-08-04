.. _testing:

=======
Testing
=======

Unit tests
----------

If you have a local development environment setup, you can run all tests via:

.. code-block:: bash

    make test

Or run individual test modules or functions via for example:

.. code-block:: bash

    SQLURI=mysql+pymysql://root:mysql@localhost/test_location \
    CELERY_ALWAYS_EAGER=true \
    bin/nosetests -s -d -v ichnaea.tests.test_geoip


Functional tests
----------------

If you have a local or remote instance of the service running, you can
send it test requests to ensure all parts of the service are running.

If you are testing a remote service, you need to look up a valid lat/lon
combination for the country you are making the request from, and substitute
the `1.23` / `3.45` values in the later examples.

First submit some new data:

.. code-block:: bash

    curl -i -k -XPOST -H "Content-Type: application/json" https://<hostname>/v1/submit?key=test -d \
    '{"items": [{"lat": 1.23, "lon": 3.45, "wifi": [{"key": "01005e901001"}, {"key": "01005e901012"}]}]}'

Which should get you a `204 No Content` response.

Right away there's no result found yet:

.. code-block:: bash

    curl -i -k -XPOST -H "Content-Type: application/json" https://<hostname>/v1/search?key=test -d \
    '{"wifi": [{"key": "01005e901001"}, {"key": "01005e901012"}]}'

Which means you get a `200 OK` response with a body of
`{"status": "not_found"}` or alternatively a GeoIP based position estimate.

After the async scheduled tasks have run (~5 every minutes), there should
be a result:

.. code-block:: bash

    curl -i -k -XPOST -H "Content-Type: application/json" https://<hostname>/v1/search?key=test -d \
    '{"wifi": [{"key": "01005e901001"}, {"key": "01005e901012"}]}'

Again a `200 OK` response with a JSON body like:

.. code-block:: javascript

    {"status": "ok", "lat": 1.23, "lon": 3.45, "accuracy": 100}
