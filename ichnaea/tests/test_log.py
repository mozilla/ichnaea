import time

from ichnaea.log import DebugStatsClient
from ichnaea.tests.base import LogTestCase


class TestStatsAPI(LogTestCase):

    def test_counter(self):
        self.stats_client.incr('metric', 2)
        self.check_stats(counter=[('metric', 1, 2)])

    def test_gauge(self):
        self.stats_client.gauge('metric', 3)
        self.check_stats(gauge=[('metric', 1, 3)])

    def test_timing(self):
        self.stats_client.timing('metric', 13)
        self.check_stats(timer=[('metric', 1, 13)])

    def test_timed(self):
        with self.stats_client.timed('metric'):
            time.sleep(0.001)
        self.check_stats(timer=[('metric', 1)])
        msg = self.stats_client.msgs[0]
        value = float(msg.split('|')[0].split(':')[1])
        self.assertTrue(0.7 < value < 10.0, msg)

    def test_mixed(self):
        self.stats_client.gauge('metric', 3)
        self.stats_client.incr('metric', 2)
        self.stats_client.timing('metric', 13)
        self.stats_client.incr('metric', 3)
        self.check_stats(
            counter=[('metric', 2)],
            gauge=['metric'],
            timer=['metric'])


class TestStatsTags(LogTestCase):

    def _make_client(self, tag_support=True, **kw):
        return DebugStatsClient(tag_support=tag_support, **kw)

    def test_one_tag(self):
        client = self._make_client()
        client.incr('metric', 1, tags=['tag:value'])
        self.check_stats(
            _client=client,
            counter=[('metric', 1, 1, ['tag:value'])])

    def test_multiple_tags(self):
        client = self._make_client()
        client.incr('metric', 1, tags=['t2:v2', 't1:v1'])
        self.check_stats(
            _client=client,
            counter=[('metric', 1, 1, ['t2:v2', 't1:v1'])])

    def test_one_tag_fallback(self):
        client = self._make_client(tag_support=False)
        client.incr('metric', 1, tags=['t1:v1'])
        self.check_stats(
            _client=client,
            counter=[('metric.t1_v1', 1, 1)])

    def test_mutiple_tags_fallback(self):
        client = self._make_client(tag_support=False)
        client.incr('metric', 1, tags=['t2:v2', 't1:v1'])
        self.check_stats(
            _client=client,
            counter=[('metric.t2_v2.t1_v1', 1, 1)])


class TestStatsPrefix(LogTestCase):

    def _make_client(self, **kw):
        return DebugStatsClient(**kw)

    def test_metric_prefix(self):
        client = self._make_client(metric_prefix='pre')
        client.incr('metric.one', 1)
        client.gauge('metric', 1)
        client.timing('metric.two.two', 2)
        self.check_stats(
            _client=client,
            counter=['pre.metric.one'],
            gauge=['pre.metric'],
            timer=['pre.metric.two.two'])
