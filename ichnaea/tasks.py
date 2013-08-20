from ichnaea.celery import celery


@celery.task(acks_late=False, ignore_result=True)
def add(x, y):
    return x + y
