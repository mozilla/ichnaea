# common base class for all data related task implementations


class DataTask(object):

    def __init__(self, task, session):
        self.task = task
        self.session = session
        self.task_shortname = task.shortname
        self.raven_client = task.raven_client
        self.redis_client = task.redis_client
        self.stats_client = task.stats_client
