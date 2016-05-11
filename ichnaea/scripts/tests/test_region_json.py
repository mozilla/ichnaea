from ichnaea.scripts import region_json


class TestRegionJson(object):

    def test_compiles(self):
        assert hasattr(region_json, 'console_entry')

    def test_guess_code(self):
        assert region_json.guess_code({'adm0_a3_is': 'SJM'}) == 'XR'
        assert region_json.guess_code({'iso_a3': 'KOS'}) == 'XK'
        assert region_json.guess_code({'iso_a3': 'AUS'}) == 'AU'
        assert region_json.guess_code({'iso_a3': 'ATA'}) == 'AQ'
        assert region_json.guess_code({'iso_a3': 'XXX'}) is None
