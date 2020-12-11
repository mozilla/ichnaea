# A script that parses the wikipedia page into JSON.
# run wget http://en.wikipedia.org/wiki/List_of_mobile_country_codes
# then this..
import json
import os

from BeautifulSoup import BeautifulSoup

from mobile_codes import MNCOperator


def parse_wikipedia():
    with open('List_of_mobile_country_codes', 'r') as htmlfile:
        soup = BeautifulSoup(htmlfile)
        operators = []

        for table in soup.findAll('table', attrs={'class': 'wikitable'}):
            for row in table.findAll('tr'):
                mcc, mnc, brand, operator = row.findChildren()[:4]
                if mcc.text in ['MCC', '']:
                    continue

                operators.append(
                    MNCOperator(
                        operator=operator.text, brand=brand.text,
                        mcc=mcc.text, mnc=mnc.text))

        return operators


def parse_itu():
    with open(os.path.join('source_data', 'itu.json'), 'rb') as jsonfile:
        return json.loads(jsonfile.read().decode())


def merge_wiki_itu():
    wiki_operators = parse_wikipedia()
    itu_operators = parse_itu()
    merged_operators = {}

    for operator in wiki_operators:
        operator_key = operator.mcc, operator.mnc
        merged_operators[operator_key] = operator

    for operator in itu_operators:
        operator_key = operator.mcc, operator.mnc
        merged_operators[operator_key] = operator

    return merged_operators.values()


def write_operators(operators):
    with open(os.path.join('mobile_codes', 'json', 'operators.json'),
              'wb') as outfile:
        outfile.write(json.dumps(operators))


if __name__ == '__main__':
    write_operators(merge_wiki_itu())
