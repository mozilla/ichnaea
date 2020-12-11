from unittest import TestCase

import mobile_codes


class TestCountries(TestCase):

    def test_mcc(self):
        countries = mobile_codes.mcc(u'302')
        self.assertEqual(len(countries), 1)
        self.assertEqual(countries[0].mcc, u'302')

    def test_mcc_multiple_codes(self):
        countries = mobile_codes.mcc(u'313')
        self.assertEqual(len(countries), 1)
        self.assertEqual(countries[0].mcc, [u'310', u'311', u'313', u'316'])

        # We even get multiple countries with multiple MCC each
        countries = mobile_codes.mcc(u'310')
        self.assertTrue(len(countries) > 1)
        for country in countries:
            self.assertTrue(len(country.mcc) > 1)

    def test_mcc_multiple_countries(self):
        countries = mobile_codes.mcc(u'505')
        self.assertEqual(len(countries), 2)

    def test_mcc_fail(self):
        countries = mobile_codes.mcc(u'000')
        self.assertEqual(len(countries), 0)

    def test_alpha2(self):
        country = mobile_codes.alpha2(u'CA')
        self.assertEqual(country.alpha2, u'CA')

    def test_alpha2_fail(self):
        self.assertRaises(KeyError, mobile_codes.alpha2, u'XX')

    def test_alpha3(self):
        country = mobile_codes.alpha3(u'CAN')
        self.assertEqual(country.alpha3, u'CAN')

    def test_alpha3_fail(self):
        self.assertRaises(KeyError, mobile_codes.alpha3, u'XYZ')

    def test_name(self):
        country = mobile_codes.name(u'canada')
        self.assertEqual(country.name, u'Canada')

    def test_name_fail(self):
        self.assertRaises(KeyError, mobile_codes.name, u'Neverland')

    def test_numeric(self):
        country = mobile_codes.numeric(u'124')
        self.assertEqual(country.numeric, u'124')

    def test_numeric_fail(self):
        self.assertRaises(KeyError, mobile_codes.numeric, u'000')

    def test_countries_match_mnc_operators(self):
        operators = mobile_codes._mnc_operators()
        operator_mccs = set([o.mcc for o in operators])
        # exclude test / worldwide mcc values
        operator_mccs -= set([u'001', u'901'])
        # exclude:
        # 312 - Northern Michigan University
        operator_mccs -= set([u'312'])

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
        self.assertEqual(countries_mccs - operator_mccs, set())

        # No operator should have a mcc value, without a matching country
        self.assertEqual(operator_mccs - countries_mccs, set())


class TestCountriesNoMCC(TestCase):

    def test_alpha2(self):
        country = mobile_codes.alpha2(u'AQ')
        self.assertEqual(country.mcc, None)

    def test_alpha3(self):
        country = mobile_codes.alpha3(u'ATA')
        self.assertEqual(country.mcc, None)

    def test_name(self):
        country = mobile_codes.name(u'antarctica')
        self.assertEqual(country.mcc, None)

    def test_numeric(self):
        country = mobile_codes.numeric(u'010')
        self.assertEqual(country.mcc, None)


class TestCountriesSpecialCases(TestCase):

    def test_puerto_rico(self):
        # Allow mainland US 310 as a valid code for Puerto Rico.
        # At least AT&T has cell networks with a mcc of 310 installed
        # in Puerto Rico, see
        # https://github.com/andymckay/mobile-codes/issues/10
        country = mobile_codes.alpha2(u'PR')
        self.assertEqual(country.mcc, [u'310', '330'])


class TestMNCOperators(TestCase):

    def test_mcc(self):
        operators = mobile_codes.operators(u'302')
        mccs = set([o.mcc for o in operators])
        self.assertEqual(mccs, set([u'302']))

    def test_mcc_fail(self):
        operators = mobile_codes.operators(u'000')
        self.assertEqual(len(operators), 0)

    def test_mcc_mnc(self):
        operator = mobile_codes.mcc_mnc(u'722', '070')
        self.assertEqual(operator.mcc, u'722')
        self.assertEqual(operator.mnc, u'070')

    def test_mcc_mnc_fail(self):
        self.assertRaises(KeyError, mobile_codes.mcc_mnc, u'000', '001')


class TestSIDOperators(TestCase):

    def test_sid_operators(self):
        operators = mobile_codes.sid_operators(u'1')
        countries = set([operator.country for operator in operators])
        mccs = set()
        for operator in operators:
            mccs = mccs.union(set([mcc for mcc in operator.mcc]))
        self.assertEquals(countries, set(['United States']))
        self.assertEquals(mccs, set([u'313', u'311', u'310', u'316']))

    def test_sid_operators_fail(self):
        operators = mobile_codes.operators(u'000')
        self.assertEqual(len(operators), 0)
