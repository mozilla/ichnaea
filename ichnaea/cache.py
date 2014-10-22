import redis
import urlparse


def redis_client(redis_url):
    url = urlparse.urlparse(redis_url)
    netloc = url.netloc.split(":")
    host = netloc[0]
    if len(netloc) > 1:
        port = int(netloc[1])
    else:  # pragma: no cover
        port = 6379
    if len(url.path) > 1:
        db = int(url.path[1:])
    else:  # pragma: no cover
        db = 0
    pool = redis.ConnectionPool(
        max_connections=100,
        host=host,
        port=port,
        db=db,
        socket_timeout=10.0,
        socket_connect_timeout=30.0,
        socket_keepalive=True,
    )
    return redis.StrictRedis(connection_pool=pool)
