# common base class for all data related task implementations


class DataTask(object):

    def __init__(self, task, session):
        self.task = task
        self.session = session
        self.task_shortname = task.shortname
        self.redis_client = task.app.redis_client
        self.stats_client = task.stats_client
