import pytest

import mobile_codes


class TestCountries:
    def test_mcc(self):
        countries = mobile_codes.mcc("302")
        assert len(countries) == 1
        assert countries[0].mcc == "302"

    def test_mcc_multiple_codes_one_country(self):
        countries = mobile_codes.mcc("312")  # US-only MCC
        assert len(countries) == 1
        assert countries[0].mcc == ["310", "311", "312", "313", "314", "315", "316"]

    def test_mcc_multiple_countries_one_code(self):
        countries = mobile_codes.mcc("313")  # MCC used in US and Puerto Rico
        assert len(countries) == 2
        actual = {country.alpha2: country.mcc for country in countries}
        assert actual == {
            "PR": ["310", "313", "330"],
            "US": ["310", "311", "312", "313", "314", "315", "316"],
        }

    def test_mcc_multiple_countries(self):
        countries = mobile_codes.mcc("505")
        assert len(countries) == 2

    def test_mcc_fail(self):
        countries = mobile_codes.mcc("000")
        assert len(countries) == 0

    def test_alpha2(self):
        country = mobile_codes.alpha2("CA")
        assert country.alpha2 == "CA"

    def test_alpha2_fail(self):
        with pytest.raises(KeyError):
            mobile_codes.alpha2("XX")

    def test_alpha3(self):
        country = mobile_codes.alpha3("CAN")
        assert country.alpha3 == "CAN"

    def test_alpha3_fail(self):
        with pytest.raises(KeyError):
            mobile_codes.alpha3("XYZ")

    def test_name(self):
        country = mobile_codes.name("canada")
        assert country.name == "Canada"

    def test_name_fail(self):
        with pytest.raises(KeyError):
            mobile_codes.name("Neverland")

    def test_numeric(self):
        country = mobile_codes.numeric("124")
        assert country.numeric == "124"

    def test_numeric_fail(self):
        with pytest.raises(KeyError):
            mobile_codes.numeric("000")

    def test_countries_match_mnc_operators(self):
        operators = mobile_codes._mnc_operators()
        operator_mccs = set([o.mcc for o in operators])

        # Exclude test MCCs
        operator_mccs -= {"001", "999"}

        # Exclude international operators
        operator_mccs -= {"901", "902", "991"}

        # Exclude FonePlus in British Indian Ocean Territory
        operator_mccs.remove("995")

        countries = mobile_codes._countries()
        countries_mccs = []
        for country in countries:
            mcc = country.mcc
            if not mcc:
                continue
            elif isinstance(mcc, list):
                countries_mccs.extend(list(mcc))
            else:
                countries_mccs.append(mcc)

        countries_mccs = set(countries_mccs)

        # No country should have a mcc value, without an operator
        assert countries_mccs - operator_mccs == set()

        # No operator should have a mcc value, without a matching country
        assert operator_mccs - countries_mccs == set()


class TestCountriesNoMCC:
    def test_alpha2(self):
        country = mobile_codes.alpha2("AQ")
        assert country.mcc is None

    def test_alpha3(self):
        country = mobile_codes.alpha3("ATA")
        assert country.mcc is None

    def test_name(self):
        country = mobile_codes.name("antarctica")
        assert country.mcc is None

    def test_numeric(self):
        country = mobile_codes.numeric("010")
        assert country.mcc is None


class TestMNCOperators:
    def test_mcc(self):
        operators = mobile_codes.operators("302")
        mccs = set([o.mcc for o in operators])
        assert mccs == {"302"}

    def test_mcc_fail(self):
        operators = mobile_codes.operators("000")
        assert len(operators) == 0

    def test_mcc_mnc(self):
        operator = mobile_codes.mcc_mnc("722", "070")
        assert operator.mcc == "722"
        assert operator.mnc == "070"

    def test_mcc_mnc_fail(self):
        with pytest.raises(KeyError):
            mobile_codes.mcc_mnc("000", "001")


class TestSIDOperators:
    def test_sid_operators(self):
        operators = mobile_codes.sid_operators("1")
        countries = set([operator.country for operator in operators])
        mccs = set()
        for operator in operators:
            mccs = mccs.union(set([mcc for mcc in operator.mcc]))
        assert countries == {"United States"}
        assert mccs == {"313", "311", "310", "316"}

    def test_sid_operators_fail(self):
        operators = mobile_codes.operators("000")
        assert len(operators) == 0
