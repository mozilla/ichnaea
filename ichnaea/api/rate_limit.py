"""A Redis based rate limit implementation."""
from redis import RedisError


def rate_limit_exceeded(redis_client, key, maxreq=0, expire=86400, on_error=False):
    """
    Return `True` if the rate limit is exceeded otherwise `False`.

    :param redis_client: A :class:`ichnaea.cache.RedisClient`
    :param key: The Redis key to be used.
    :param maxreq: The maximum number of requests.
    :param expire: How many seconds should the Redis key be retained.
    :param on_error: If Redis could not be connected, report this
                     as the return status.
    """
    if maxreq:
        try:
            with redis_client.pipeline() as pipe:
                pipe.incr(key, 1)
                pipe.expire(key, expire)
                count, expire = pipe.execute()
                return count > maxreq
        except RedisError:  # pragma: no cover
            # If we cannot connect to Redis, return error value.
            return on_error
    return False
