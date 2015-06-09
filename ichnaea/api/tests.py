from colander import MappingSchema, String

from ichnaea.api.schema import InternalSchemaNode, InternalMapping
from ichnaea.tests.base import TestCase


class InternalSchemaNodeTests(TestCase):

    def test_internal_schema_node_uses_internal_name(self):

        class SampleSchema(MappingSchema):
            schema_type = InternalMapping

            input_name = InternalSchemaNode(
                String(), internal_name='output_name')

            def __init__(self, *args, **kwargs):
                super(SampleSchema, self).__init__(*args, **kwargs)

        input_data = {
            'input_name': 'value',
        }

        output_data = SampleSchema().deserialize(input_data)
        self.assertEqual(output_data['output_name'], 'value')
        self.assertFalse('input_name' in output_data)
