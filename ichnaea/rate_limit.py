from redis import ConnectionError


def rate_limit(redis_client, key, maxreq=0, expire=86400, fail_on_error=False):
    if maxreq:
        try:
            with redis_client.pipeline() as pipeline:
                pipeline.incr(key, 1)
                pipeline.expire(key, expire)
                count, expire = pipeline.execute()
                return count > maxreq
        except ConnectionError:  # pragma: no cover
            # If we cannot connect to Redis, disable rate limitation.
            return fail_on_error
