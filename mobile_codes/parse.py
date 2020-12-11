#!/usr/bin/env python3

# A script that parses the wikipedia pages and other sources into JSON.
# run download_data.sh which will run this
import json
import os
import sys
import iso3166
import re
import requests
from bs4 import BeautifulSoup
from collections import defaultdict, namedtuple, OrderedDict

MNC_OPERATOR_FIELDS = ('mcc', 'mnc', 'brand', 'operator')
COUNTRY_FIELDS = ('name', 'iso2', 'iso3', 'numeric', 'mccs')
MNC_OPERATOR_FIELDS_ISO = ('mcc', 'mnc', 'brand', 'operator', 'iso')
MNC_FIELDS_ITU = ('mcc', 'mnc', 'brand', 'country')
MNCOperatorISO = namedtuple('MNCOperatorISO', MNC_OPERATOR_FIELDS_ISO)
MNCOperatorITU = namedtuple('MNCOperatorITU', MNC_FIELDS_ITU)
MNCOperator = namedtuple('MNCOperator', MNC_OPERATOR_FIELDS)
CountriesD = namedtuple('CountryD', COUNTRY_FIELDS)
_CACHE = {}

def _load_json(cache_key, json_path, wrapper):
    global _CACHE
    if cache_key not in _CACHE:
        with open(json_path, 'rb') as json_file:
            data = json.loads(json_file.read().decode())
            _CACHE[cache_key] = [
                wrapper(*line) for line in data]
    return _CACHE[cache_key]


def parse_wikipedia():
    operators = []

    subpages = []
    try:
        response = requests.get('https://en.wikipedia.org/wiki/Mobile_country_code', timeout=30)
        response.raise_for_status()
    except HTTPError as http_err:
        print("HTTP error occurred: {}".format(http_err))
        sys.exit(1)
    except Exception as err:
        print("Other error occurred: {}".format(err))
        sys.exit(1)
    else:
        htmlfile = response.text
    soup = BeautifulSoup(htmlfile, 'html.parser')
    for table in soup.find_all('table', class_="wikitable"):
        for links in table.find_all('a', href=True):
            if links.text.startswith('List of mobile network codes in'):
                match = re.search('(.+?)#',links['href'])
                if match:
                    url = match.group(1)
                    if url not in subpages:
                        subpages.append(url)
    subpages.sort()
    wikifiles = len(subpages)
    i = 0
    while i <= wikifiles:
        if (i > 0):
            try:
                response = requests.get('https://en.wikipedia.org' + subpages[i - 1], timeout=30)
                response.raise_for_status()
            except HTTPError as http_err:
                print("HTTP error occurred: {}".format(http_err))
                sys.exit(1)
            except Exception as err:
                print("Other error occurred: {}".format(err))
                sys.exit(1)
            else:
                htmlfile = response.text
            soup = BeautifulSoup(htmlfile, 'html.parser')
        for table in soup.find_all('table', class_="wikitable", attrs={'width': "100%"}):
            hs = table.find_previous_sibling('h4')
            iso = ""
            if hs is not None:
                hs = hs.find('span', class_="mw-headline")
                if hs is not None:
                    if hs.a is not None:
                        i_tag = hs.a
                        i_tag.decompose()
                    iso = re.sub(r'\(.*\)', "", hs.text.strip().strip('\n').replace('\n','').replace('–','').replace(' ',''))
                    if iso == "GE-AB":
                        iso = "GE"
                    if "-" in iso:
                        print("Another iso with region code, please check !: " + iso)
            for row in table.find_all('tr'):
                mcc, mnc, brand, operator = row.find_all_next("td", limit=4)
                if mcc.text in ['MCC', '']:
                    continue
                if mcc.div is not None:
                    i_tag = mcc.div
                    i_tag.decompose()
                if mcc.span is not None:
                    i_tag = mcc.span
                    i_tag.decompose()
                mcc = mcc.text.strip().strip('\n').replace('\n','')
                if mnc.div is not None:
                    i_tag = mnc.div
                    i_tag.decompose()
                if mnc.span is not None:
                    i_tag = mnc.span
                    i_tag.decompose()
                mnc = mnc.text.strip().strip('\n').replace('\n','')
                if operator.div is not None:
                    i_tag = operator.div
                    i_tag.decompose()
                if operator.span is not None:
                    i_tag = operator.span
                    i_tag.decompose()
                operator = operator.text.strip().strip('\n').replace('\n','')
                if brand.div is not None:
                    i_tag = brand.div
                    i_tag.decompose()
                if brand.span is not None:
                    i_tag = brand.span
                    i_tag.decompose()
                brand = brand.text.strip().strip('\n').replace('\n','')
                operators.append(MNCOperatorISO(mcc=mcc, mnc=mnc, brand=brand, operator=operator, iso=iso))
        i += 1
    return operators

def parse_itu():
    # The itu.json file was created from the English word document: https://www.itu.int/dms_pub/itu-t/opb/sp/T-SP-E.212B-2018-MSW-E.docx
    return _load_json(
        'itu.json', os.path.join('source_data', 'itu.json'),  MNCOperatorITU)

def parse_mcc_mnc_table():
    try:
        response = requests.get('https://raw.githubusercontent.com/musalbas/mcc-mnc-table/master/mcc-mnc-table.json', timeout=30)
        response.raise_for_status()
    except HTTPError as http_err:
        print("HTTP error occurred: {}".format(http_err))
        sys.exit(1)
    except Exception as err:
        print("Other error occurred: {}".format(err))
        sys.exit(1)
    else:
        jsonfile = response.text
    if len(jsonfile) > 0:
        return json.loads(jsonfile)
    else:
        return {}


def merge_wiki_itu():
    wiki_operators = parse_wikipedia()
    itu_operators = parse_itu()
    mcc_mnc_operators = parse_mcc_mnc_table()
    merged_operators = {}
    sorted_operators = OrderedDict()
    country_dict = {}
    country_list = iso3166.countries
    countries_sorted = OrderedDict()
    for country in country_list:
        country_dict[country.alpha2] = CountriesD._make([country.name, country.alpha2, country.alpha3, country.numeric, None])

    for operator_itu in itu_operators:
        cname = operator_itu.country
        # rename the country names to match them with the ones from iso3166
        cname = cname.replace('*','')
        cname = cname.replace('Czech Rep.','Czechia')
        cname = cname.replace('Rep.','Republic')
        cname = cname.replace('United Kingdom','United Kingdom of Great Britain and Northern Ireland')
        cname = cname.replace(' (',', ').replace(')','')
        cname = cname.replace('The Former Yugoslav Republic of Macedonia','North Macedonia')
        cname = cname.replace('United States','United States of America')
        cname = cname.replace('British Virgin Islands','Virgin Islands, British')
        cname = cname.replace('Dem. Republic of the Congo','Congo, Democratic Republic of the')
        cname = cname.replace('Tanzania','Tanzania, United Republic of')
        cname = cname.replace('Hong Kong, China','Hong Kong')
        cname = cname.replace('Macao, China','Macao')
        cname = cname.replace('Lao P.D.R.','Lao People\'s Democratic Republic')
        cname = cname.replace('Micronesia','Micronesia, Federated States of')
        cname = cname.replace('French Departments and Territories in the Indian Ocean','French Southern Territories')
        cname = cname.replace('Falkland Islands, Malvinas', 'Falkland Islands (Malvinas)')
        country = None
        if cname != "":
            country = country_list.get(cname)
        if country is not None:
            iso = country.alpha2
            if country_dict[iso] is not None:
                c = country_dict[iso]
                if c.mccs is None:
                    c = c._replace(mccs = operator_itu.mcc)
                else:
                    if operator_itu.mcc not in c.mccs:
                        if isinstance(c.mccs, list):
                            xmcc = list(c.mccs)
                        else:
                            xmcc = [c.mccs]
                        xmcc.append(operator_itu.mcc)
                        c = c._replace(mccs = xmcc)
                country_dict[iso] = c
        operator = MNCOperator._make([operator_itu.mcc, operator_itu.mnc, operator_itu.brand, operator_itu.brand])
        operator_key = operator.mcc, operator.mnc
        merged_operators[operator_key] = list(operator._asdict().values())

    for operator_mcc_mnc in mcc_mnc_operators:
        iso = operator_mcc_mnc["iso"].upper()
        # fix some iso2 country codes
        if iso == "FG":
            iso = "GF"
        if iso == "AN":
            iso = "BQ"
        if iso == "TP":
            iso = "TL"
        if iso == "TK" and operator_mcc_mnc["country"].upper() == "TAJIKISTAN":
            iso = "TJ"
        if iso == "VI" and operator_mcc_mnc["mcc"] == "376":
            iso = "TC"
        if iso == "N/A":
            iso = None
        if iso is not None:
            if country_dict[iso] is not None:
                c = country_dict[iso]
                if c.mccs is None:
                    c = c._replace(mccs = operator_mcc_mnc["mcc"])
                else:
                    if operator_mcc_mnc["mcc"] not in c.mccs:
                        if isinstance(c.mccs, list):
                            xmcc = list(c.mccs)
                        else:
                            xmcc = [c.mccs]
                        xmcc.append(operator_mcc_mnc["mcc"])
                        c = c._replace(mccs = xmcc)
                country_dict[iso] = c
        operator = MNCOperator._make([operator_mcc_mnc["mcc"], operator_mcc_mnc["mnc"], operator_mcc_mnc["network"], operator_mcc_mnc["network"]])
        operator_key = operator.mcc, operator.mnc
        merged_operators[operator_key] = list(operator._asdict().values())

    for operator_iso in wiki_operators:
        if operator_iso.iso is not None and operator_iso.iso != "":
            isos = operator_iso.iso.split("/")
            if isos is None:
                print("fallback")
                isos = iso
            for iso in isos:
                if country_dict[iso] is not None:
                    c = country_dict[iso]
                    if c.mccs is None:
                        c = c._replace(mccs = operator_iso.mcc)
                    else:
                        if operator_iso.mcc not in c.mccs:
                            if isinstance(c.mccs, list):
                                xmcc = list(c.mccs)
                            else:
                                xmcc = [c.mccs]
                            xmcc.append(operator_iso.mcc)
                            c = c._replace(mccs = xmcc)
                    country_dict[iso] = c
        operator = MNCOperator._make([operator_iso.mcc, operator_iso.mnc, operator_iso.brand, operator_iso.operator])
        operator_key = operator.mcc, operator.mnc
        merged_operators[operator_key] = list(operator._asdict().values())

    for key, value in sorted(country_dict.items(), key=lambda t: t[1]):
        x_list = list(value._asdict().values())
        if isinstance(x_list[4], list):
            x_sorted = sorted(x_list[4])
        else:
            x_sorted = x_list[4]
        x_list[4] = x_sorted
        countries_sorted[key] = x_list
    with open(os.path.join('mobile_codes', 'json', 'countries.json'),'w') as outfile:
        json_string = json.dumps(list(countries_sorted.values()), ensure_ascii=True)
        # Should be a better way to obtain the desired custom pretty formatted json file, maybe with a custom class ...
        json_string = re.sub(r'\], \[', '],\n    [', json_string)
        json_string = re.sub(r'\]\]$',']\n]',json_string)
        json_string = re.sub(r'\[\[','[\n    [',json_string) + '\n'
        outfile.write(json_string)
    for key, value in sorted(merged_operators.items()):
        sorted_operators[key] = value
    return list(sorted_operators.values())

def write_operators(operators):
    with open(os.path.join('mobile_codes', 'json', 'mnc_operators.json'),
              'w') as outfile:
        json_string = json.dumps(operators, ensure_ascii=True)
        # Should be a better way to obtain the desired custom pretty formatted json file, maybe with a custom class ...
        json_string = re.sub(r'\], \[', '],\n    [', json_string)
        json_string = re.sub(r'\]\]$',']\n]',json_string)
        json_string = re.sub(r'\[\[','[\n    [',json_string) + '\n'
        outfile.write(json_string)

if __name__ == '__main__':
    write_operators(merge_wiki_itu())
