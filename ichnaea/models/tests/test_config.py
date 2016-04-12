import uuid

from ichnaea.models.config import ExportConfig
from ichnaea.tests.base import DBTestCase


class TestExportConfig(DBTestCase):

    def test_fields(self):
        skips = [uuid.uuid4().hex for i in range(3)]
        self.session.add(ExportConfig(
            name='internal', batch=100,
            schema='internal', url='internal://', skip_keys=skips,
        ))
        self.session.flush()

        result = self.session.query(ExportConfig).get('internal')
        self.assertEqual(result.name, 'internal')
        self.assertEqual(result.batch, 100)
        self.assertEqual(result.schema, 'internal')
        self.assertEqual(result.url, 'internal://')
        self.assertEqual(result.skip_keys, frozenset(skips))

    def test_skip_keys(self):
        non_ascii = b'\xc3\xa4'.decode('utf-8')
        configs = [
            ExportConfig(name='none', skip_keys=None),
            ExportConfig(name='list', skip_keys=[]),
            ExportConfig(name='set', skip_keys=set()),
            ExportConfig(name='one', skip_keys=['ab']),
            ExportConfig(name='two', skip_keys=['ab', 'cd']),
            ExportConfig(name='unicode', skip_keys=['ab', non_ascii]),
        ]
        self.session.add_all(configs)
        self.session.commit()

        def test(name, expected):
            row = (self.session.query(ExportConfig)
                               .filter(ExportConfig.name == name)).first()
            self.assertEqual(row.skip_keys, expected)

        test('none', None)
        test('list', frozenset())
        test('set', frozenset())
        test('one', frozenset(['ab']))
        test('two', frozenset(['ab', 'cd']))
        test('unicode', frozenset(['ab', non_ascii]))
