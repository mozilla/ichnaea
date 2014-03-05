from loads.case import TestCase


class TestWebSite(TestCase):
    def test_submit_cell_data(self):
        for data in open('sample_data.json', 'r'):
            data = data.strip()
            res = self.session.post('http://localhost:7001/v1/submit', data)
            self.assertEqual(res.status_code, 204)
