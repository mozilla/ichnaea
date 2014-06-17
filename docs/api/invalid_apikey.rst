For API key mismatches we return a `keyInvalid` message with an HTTP
400 error. The JSON response should be:

.. code-block:: javascript

    {
        "error": {
            "errors": [{
                "domain": "usageLimits",
                "reason": "keyInvalid",
                "message": "Missing or invalid API key.",
            }],
            "code": 400,
            "message": "Invalid API key",
        }
    }
