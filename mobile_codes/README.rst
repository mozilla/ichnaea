This code was originally hosted at
`andymckay/mobile-codes <https://github.com/andymckay/mobile-codes>`_,
and published as
`mobile-codes <https://pypi.org/project/mobile-codes/>`_. It was marked
unmaintained in December 2016. The original code is licensed under
`Mozilla Public License 2.0 <https://www.mozilla.org/en-US/MPL/2.0/>`_,
with additional code. See ``LICENSE.txt`` for details.

Contains the country codes from ISO 3166-1 based on the code based on:

https://github.com/deactivated/python-iso3166/

But also has the MCC and MNC codes based on the Wikipedia page:

http://en.wikipedia.org/wiki/List_of_mobile_country_codes

As well as the latest released listing from ITU:

http://www.itu.int/dms_pub/itu-t/opb/sp/T-SP-E.212B-2014-PDF-E.pdf

Note that MCC codes for a country can be:

* None (no MCC code)
* a string (where a country has one code)
* a tuple of strings (where a country has more than one code)


Usage
=====

Lookup by Mobile Country Code (MCC)::

    >>> mobile_codes.mcc("648")
    [Country(name=u'Zimbabwe', alpha2='ZW', alpha3='ZWE', numeric='716', mcc='648')]
    >>> mobile_codes.mcc("311")
    [Country(name=u'Guam', alpha2='GU', alpha3='GUM', numeric='316', mcc=('310', '311')),
     Country(name=u'United States', alpha2='US', alpha3='USA', numeric='840', mcc=('310', '311', '313', '316'))]
    >>> mobile_codes.mcc("313")
    [Country(name=u'United States', alpha2='US', alpha3='USA', numeric='840', mcc=('310', '311', '313', '316'))]

Lookup by name, alpha2, alpha3 (all case insensitive)::

    >>> mobile_codes.alpha3("CAN")
    Country(name=u'Canada', alpha2='CA', alpha3='CAN', numeric='124', mcc='302')
    >>> mobile_codes.alpha2("CA")
    Country(name=u'Canada', alpha2='CA', alpha3='CAN', numeric='124', mcc='302')
    >>> mobile_codes.name('canada')
    Country(name=u'Canada', alpha2='CA', alpha3='CAN', numeric='124', mcc='302')

Lookup operators by mcc (returns a list of all operators)::

    >>> mobile_codes.operators('302')
    [Operator(mcc='302', mnc='220', brand='Telus', operator=u'Telus'),
     Operator(mcc='302', mnc='221', brand='Telus', operator=u'Telus'),...

Lookup operator by mcc and Mobile Network Code (MNC)::

    >>> mobile_codes.mcc_mnc('722', '070')
    Operator(mcc='722', mnc='070', brand='Movistar', operator=u'Movistar')

All lookups raise a KeyError if the requested value is not found.

Contributors
============

* Andy McKay (`andymckay <https://github.com/andymckay>`_)
* Hanno Schlichting (`hannosch <https://github.com/hannosch>`_)
* Jared Kerim (jaredkerim)
