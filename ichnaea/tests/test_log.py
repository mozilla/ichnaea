import time

from ichnaea.log import DebugStatsClient


class TestStatsAPI(object):

    def test_counter(self, stats):
        stats.incr('metric', 2)
        stats.check(counter=[('metric', 1, 2)])

    def test_gauge(self, stats):
        stats.gauge('metric', 3)
        stats.check(gauge=[('metric', 1, 3)])

    def test_timing(self, stats):
        stats.timing('metric', 13)
        stats.check(timer=[('metric', 1, 13)])

    def test_timed(self, stats):
        with stats.timed('metric'):
            time.sleep(0.001)
        stats.check(timer=[('metric', 1)])
        msg = stats.msgs[0]
        value = float(msg.split('|')[0].split(':')[1])
        assert 0.7 < value < 10.0

    def test_mixed(self, stats):
        stats.histogram('metric', 5)
        stats.gauge('metric', 3)
        stats.incr('metric', 2)
        stats.set('metric', 7)
        stats.timing('metric', 13)
        stats.incr('metric', 3)
        stats.check(
            counter=[('metric', 2)],
            gauge=['metric'],
            histogram=['metric'],
            set=['metric'],
            timer=['metric'])


class TestStatsTags(object):

    def _make_client(self, tag_support=True, **kw):
        return DebugStatsClient(tag_support=tag_support, **kw)

    def test_one_tag(self):
        client = self._make_client()
        client.incr('metric', 1, tags=['tag:value'])
        client.check(
            counter=[('metric', 1, 1, ['tag:value'])])

    def test_multiple_tags(self):
        client = self._make_client()
        client.incr('metric', 1, tags=['t2:v2', 't1:v1'])
        client.check(
            counter=[('metric', 1, 1, ['t2:v2', 't1:v1'])])

    def test_one_tag_fallback(self):
        client = self._make_client(tag_support=False)
        client.incr('metric', 1, tags=['t1:v1'])
        client.check(
            counter=[('metric.t1_v1', 1, 1)])

    def test_mutiple_tags_fallback(self):
        client = self._make_client(tag_support=False)
        client.incr('metric', 1, tags=['t2:v2', 't1:v1'])
        client.check(
            counter=[('metric.t2_v2.t1_v1', 1, 1)])


class TestStatsNamespace(object):

    def _make_client(self, **kw):
        return DebugStatsClient(**kw)

    def test_namespace(self):
        client = self._make_client(namespace='pre')
        client.incr('metric.one', 1)
        client.gauge('metric', 1)
        client.timing('metric.two.two', 2)
        client.check(
            counter=['pre.metric.one'],
            gauge=['pre.metric'],
            timer=['pre.metric.two.two'])
