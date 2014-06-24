import redis
import urlparse


def redis_con(redis_url, registry):
    r_url = urlparse.urlparse(redis_url)
    r_host = r_url.netloc.split(":")[0]
    r_port = int(r_url.netloc.split(":")[1])
    r_db = int(r_url.path[1:])
    pool = redis.ConnectionPool(
        max_connections=100,
        socket_timeout=10.0,
        socket_connect_timeout=30.0,
        socket_keepalive=True,
    )
    registry.redis_pool = pool
    return redis.StrictRedis(host=r_host,
                             port=r_port,
                             db=r_db,
                             connection_pool=pool)
