from ichnaea.geocode import GEOCODER
from ichnaea.models.constants import ALL_VALID_MCCS


class TestGeocoder(object):
    def test_no_region(self):
        func = GEOCODER.region
        assert func(-60.0, 11.0) is None
        assert func(0.0, 0.0) is None
        assert func(36.4173, 18.728) is None
        assert func(48.3, -7.0) is None

    def test_region(self):
        func = GEOCODER.region
        assert func(31.522, 34.455) == "XW"
        assert func(42.83256, 20.34221) == "RS"
        assert func(42.4255, 3.3584) == "ES"
        assert func(46.2130, 6.1290) == "FR"
        assert func(46.5743, 6.3532) == "FR"
        assert func(48.8656, 13.6781) == "CZ"
        assert func(49.7089, 6.0741) == "LU"
        assert func(51.5142, -0.0931) == "GB"
        assert func(60.1, 20.0) == "FI"

    def test_in_region(self):
        func = GEOCODER.in_region
        assert func(51.5142, -0.0931, "GB")
        assert not func(0.0, 0.0, "GB")
        assert not func(60.1, 20.0, "AX")

    def test_in_region_mcc(self):
        func = GEOCODER.in_region_mcc
        assert func(51.5142, -0.0931, 234)
        assert func(51.5142, -0.0931, 235)
        assert not func(0.0, 0.0, 234)

    def test_region_for_cell(self):
        func = GEOCODER.region_for_cell
        assert func(51.5142, -0.0931, 234) == "GB"
        assert func(51.5142, -0.0931, 235) == "GB"
        assert func(46.2130, 6.1290, 228) == "CH"
        assert func(46.5743, 6.3532, 208) == "FR"
        assert func(31.522, 34.455, 425) == "XW"
        assert func(0.0, 0.0, 234) is None

    def test_region_for_code(self):
        func = GEOCODER.region_for_code
        assert func("GB").code == "GB"
        assert func("CH").code == "CH"
        assert func("XX") is None
        assert func(None) is None

    def test_max_radius(self):
        assert GEOCODER.region_max_radius("US") == 2971000.0
        assert GEOCODER.region_max_radius("LI") == 14000.0
        assert GEOCODER.region_max_radius("VA") == 1000.0

    def test_max_radius_fail(self):
        for invalid in (None, 42, "A", "us", "USA", "AA"):
            assert GEOCODER.region_max_radius(invalid) is None


class TestRegionsForMcc(object):
    def test_no_match(self):
        assert GEOCODER.regions_for_mcc(None) == []
        assert GEOCODER.regions_for_mcc(None, metadata=True) == []
        assert GEOCODER.regions_for_mcc(1) == []
        assert GEOCODER.regions_for_mcc(1, metadata=True) == []
        assert GEOCODER.regions_for_mcc("") == []
        assert GEOCODER.regions_for_mcc("1", metadata=True) == []

    def test_single(self):
        assert set(GEOCODER.regions_for_mcc(262)) == set(["DE"])
        regions = GEOCODER.regions_for_mcc(262, metadata=True)
        assert set([r.code for r in regions]) == set(["DE"])

    def test_multiple(self):
        assert set(GEOCODER.regions_for_mcc(311)) == {"AS", "GU", "US"}
        regions = GEOCODER.regions_for_mcc(311, metadata=True)
        assert set([r.code for r in regions]) == {"AS", "GU", "US"}

    def test_filtered(self):
        # AX / Aland Islands is not in the GENC list
        assert set(GEOCODER.regions_for_mcc(244)) == set(["FI"])

    def test_all_valid_mcc(self):
        for mcc in ALL_VALID_MCCS:
            regions = set(GEOCODER.regions_for_mcc(mcc))
            assert regions != set()
            assert regions - GEOCODER._valid_regions == set()
