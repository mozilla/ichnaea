from colander import MappingSchema, String
from pyramid.request import Request

from ichnaea.api.exceptions import LocationNotFound
from ichnaea.api.schema import InternalSchemaNode, InternalMapping
from ichnaea.tests.base import TestCase


class TestInternalSchemaNode(TestCase):

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


class TestExceptions(TestCase):

    def test_exception_rendering(self):
        # make sure all the sub-classing returns what we expect
        error = LocationNotFound()
        self.assertEqual(str(error), '<LocationNotFound>: 404')

        response = Request.blank('/').get_response(error)

        self.assertEqual(response.status_code, 404)
        self.assertEqual(response.content_type, 'application/json')
        self.assertEqual(response.json, LocationNotFound.json_body())
        self.assertTrue('404' in response.body)
        self.assertTrue('notFound' in response.body)
