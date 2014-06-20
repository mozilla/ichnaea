import redis
import urlparse


def redis_con(redis_url, registry):
    r_url = urlparse.urlparse(redis_url)
    r_host = r_url.netloc.split(":")[0]
    r_port = int(r_url.netloc.split(":")[1])
    r_db = int(r_url.path[1:])
    pool = redis.ConnectionPool(max_connections=100)
    registry.redis_pool = pool
    return redis.StrictRedis(host=r_host,
                             port=r_port,
                             db=r_db,
                             connection_pool=pool)
