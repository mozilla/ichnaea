"""shard cell table

Revision ID: d350610e27e
Revises: 40d609897296
Create Date: 2015-11-26 12:53:31.278039
"""

import codecs
import logging
import struct

from alembic import op
import sqlalchemy as sa


log = logging.getLogger('alembic.migration')
revision = 'd350610e27e'
down_revision = '40d609897296'

CELLAREA_STRUCT = struct.Struct('!bHHH')

MCC_TO_REGION = {
    202: 'GR',
    204: 'NL',
    206: 'BE',
    212: 'MC',
    213: 'AD',
    214: 'ES',
    216: 'HU',
    218: 'BA',
    219: 'HR',
    220: 'RS',
    222: 'IT',
    225: 'VA',
    226: 'RO',
    228: 'CH',
    230: 'CZ',
    231: 'SK',
    232: 'AT',
    235: 'GB',
    238: 'DK',
    240: 'SE',
    242: 'NO',
    244: 'FI',
    246: 'LT',
    247: 'LV',
    248: 'EE',
    250: 'RU',
    255: 'UA',
    257: 'BY',
    259: 'MD',
    260: 'PL',
    262: 'DE',
    266: 'GI',
    268: 'PT',
    270: 'LU',
    272: 'IE',
    274: 'IS',
    276: 'AL',
    278: 'MT',
    280: 'CY',
    282: 'GE',
    283: 'AM',
    284: 'BG',
    286: 'TR',
    288: 'FO',
    289: 'GE',
    290: 'GL',
    292: 'SM',
    293: 'SI',
    294: 'MK',
    295: 'LI',
    297: 'ME',
    302: 'CA',
    308: 'PM',
    313: 'US',
    316: 'US',
    330: 'PR',
    334: 'MX',
    342: 'BB',
    344: 'AG',
    346: 'KY',
    348: 'VG',
    350: 'BM',
    352: 'GD',
    354: 'MS',
    356: 'KN',
    358: 'LC',
    360: 'VC',
    363: 'AW',
    364: 'BS',
    365: 'AI',
    366: 'DM',
    368: 'CU',
    370: 'DO',
    372: 'HT',
    374: 'TT',
    376: 'TC',
    400: 'AZ',
    401: 'KZ',
    402: 'BT',
    404: 'IN',
    405: 'IN',
    410: 'PK',
    412: 'AF',
    413: 'LK',
    414: 'MM',
    415: 'LB',
    416: 'JO',
    417: 'SY',
    418: 'IQ',
    419: 'KW',
    420: 'SA',
    421: 'YE',
    422: 'OM',
    424: 'AE',
    426: 'BH',
    427: 'QA',
    428: 'MN',
    429: 'NP',
    432: 'IR',
    434: 'UZ',
    436: 'TJ',
    437: 'KG',
    438: 'TM',
    440: 'JP',
    441: 'JP',
    450: 'KR',
    452: 'VN',
    454: 'HK',
    455: 'MO',
    456: 'KH',
    457: 'LA',
    460: 'CN',
    466: 'TW',
    467: 'KP',
    470: 'BD',
    472: 'MV',
    502: 'MY',
    510: 'ID',
    514: 'TL',
    515: 'PH',
    520: 'TH',
    525: 'SG',
    528: 'BN',
    530: 'NZ',
    536: 'NR',
    537: 'PG',
    539: 'TO',
    540: 'SB',
    541: 'VU',
    542: 'FJ',
    544: 'AS',
    545: 'KI',
    546: 'NC',
    547: 'PF',
    548: 'CK',
    549: 'WS',
    550: 'FM',
    551: 'MH',
    552: 'PW',
    553: 'TV',
    555: 'NU',
    602: 'EG',
    603: 'DZ',
    605: 'TN',
    606: 'LY',
    607: 'GM',
    608: 'SN',
    609: 'MR',
    610: 'ML',
    611: 'GN',
    612: 'CI',
    613: 'BF',
    614: 'NE',
    615: 'TG',
    616: 'BJ',
    617: 'MU',
    618: 'LR',
    619: 'SL',
    620: 'GH',
    621: 'NG',
    622: 'TD',
    623: 'CF',
    624: 'CM',
    625: 'CV',
    626: 'ST',
    627: 'GQ',
    628: 'GA',
    629: 'CG',
    630: 'CD',
    631: 'AO',
    632: 'GW',
    633: 'SC',
    634: 'SD',
    635: 'RW',
    636: 'ET',
    637: 'SO',
    638: 'DJ',
    639: 'KE',
    640: 'TZ',
    641: 'UG',
    642: 'BI',
    643: 'MZ',
    645: 'ZM',
    646: 'MG',
    647: 'RE',
    648: 'ZW',
    649: 'NA',
    650: 'MW',
    651: 'LS',
    652: 'BW',
    653: 'SZ',
    654: 'KM',
    655: 'ZA',
    657: 'ER',
    659: 'SS',
    702: 'BZ',
    704: 'GT',
    706: 'SV',
    708: 'HN',
    710: 'NI',
    712: 'CR',
    714: 'PA',
    716: 'PE',
    722: 'AR',
    724: 'BR',
    730: 'CL',
    732: 'CO',
    734: 'VE',
    736: 'BO',
    738: 'GY',
    740: 'EC',
    744: 'PY',
    746: 'SR',
    748: 'UY',
    750: 'FK',
}

stmt_drop_index = '''\
ALTER TABLE cell_{id}
DROP KEY `cell_{id}_created_idx`,
DROP KEY `cell_{id}_modified_idx`,
DROP KEY `cell_{id}_latlon_idx`,
DROP KEY `cell_{id}_region_idx`
'''

stmt_add_index = '''\
ALTER TABLE cell_{id}
ADD INDEX `cell_{id}_created_idx` (`created`),
ADD INDEX `cell_{id}_modified_idx` (`modified`),
ADD INDEX `cell_{id}_latlon_idx` (`lat`,`lon`),
ADD INDEX `cell_{id}_region_idx` (`region`)
'''

stmt_optimize = '''\
OPTIMIZE TABLE cell_{id}
'''

stmt_insert = '''\
INSERT INTO cell_{id} (
`cellid`,
`radio`, `mcc`, `mnc`, `lac`, `cid`, `psc`,
`lat`, `lon`, `radius`, `max_lat`, `min_lat`, `max_lon`, `min_lon`,
`samples`, `created`, `modified`) (
SELECT
UNHEX(CONCAT(
LPAD(HEX(`radio`), 2, 0), LPAD(HEX(`mcc`), 4, 0),
LPAD(HEX(`mnc`), 4, 0), LPAD(HEX(`lac`), 4, 0),
LPAD(HEX(`cid`), 8, 0))),
`radio`, `mcc`, `mnc`, `lac`, `cid`, `psc`,
`lat`, `lon`, `radius`, `max_lat`, `min_lat`, `max_lon`, `min_lon`,
`samples`, `created`, `modified`
FROM cell WHERE `radio` = {radio}
)
'''

stmt_update_regions = '''\
UPDATE cell_{id}
SET `region` = "{code}"
WHERE `radio` IN (0, 1, 2, 3) AND `mcc` = {mcc}
'''

stmt_region_count = '''\
SELECT COUNT(*) FROM cell_{id} WHERE region IS NULL
'''

stmt_select_region = '''\
SELECT HEX(`cellid`), `mcc`, `lat`, `lon`
FROM cell_{id}
WHERE `region` IS NULL
LIMIT {batch}
'''

stmt_update_region = '''\
UPDATE cell_{id}
SET `region` = "{code}"
WHERE `cellid` in ({ids})
'''

stmt_delete_outside = '''\
DELETE FROM cell_{id}
WHERE `cellid` in ({ids})
'''

stmt_select_area = '''\
SELECT
AVG(`lat`) AS `lat`,
AVG(`lon`) AS `lon`,
AVG(`radius`) AS `avg_cell_radius`,
COUNT(*) as `num_cells`,
MIN(`min_lat`) AS `min_lat`,
MAX(`max_lat`) AS `max_lat`,
MIN(`min_lon`) AS `min_lon`,
MAX(`max_lon`) AS `max_lon`
FROM cell_{id}
WHERE `radio` = {radio} AND `mcc` = {mcc} AND `mnc` = {mnc} AND `lac` = {lac}
'''

stmt_update_area = '''\
UPDATE cell_area SET
`lat` = {lat},
`lon` = {lon},
`radius` = {radius},
`avg_cell_radius` = {avg_cell_radius},
`num_cells` = {num_cells}
WHERE `radio` = {radio} AND `mcc` = {mcc} AND `mnc` = {mnc} AND `lac` = {lac}
'''

stmt_delete_area = '''\
DELETE FROM cell_area
WHERE `radio` = {radio} AND `mcc` = {mcc} AND `mnc` = {mnc} AND `lac` = {lac}
'''

stmt_select_stat = '''\
SELECT * FROM stat
WHERE `key` = 2
ORDER BY `time` DESC LIMIT 1
'''

stmt_update_stat = '''\
UPDATE stat
SET `value` = {value}
WHERE `key` = 2 AND `time` = {time}
'''


def _update_area(bind, shard_id, areaid, circle_radius):
    radio, mcc, mnc, lac = CELLAREA_STRUCT.unpack(codecs.decode(areaid, 'hex'))
    row = bind.execute(sa.text(stmt_select_area.format(
        id=shard_id, radio=radio, mcc=mcc, mnc=mnc, lac=lac))).fetchone()
    num_cells = int(row.num_cells)
    if num_cells == 0:
        op.execute(sa.text(stmt_delete_area.format(
            radio=radio, mcc=mcc, mnc=mnc, lac=lac)))
    else:
        radius = circle_radius(
            float(row.lat), float(row.lon),
            float(row.max_lat), float(row.max_lon),
            float(row.min_lat), float(row.min_lon))
        avg_cell_radius = int(round(row.avg_cell_radius))

        op.execute(sa.text(stmt_update_area.format(
            radio=radio, mcc=mcc, mnc=mnc, lac=lac,
            lat=float(row.lat), lon=float(row.lon), radius=radius,
            avg_cell_radius=avg_cell_radius, num_cells=num_cells,
        )))


def _update_stat(bind, deleted_total):
    row = bind.execute(sa.text(stmt_select_stat)).fetchone()
    if row:
        new_value = row.value - deleted_total
        op.execute(sa.text(stmt_update_stat.format(
            time=row.time, value=new_value)))


def _update_region_batch(bind, shard_id, geocoder, batch=10000):
    rows = bind.execute(sa.text(stmt_select_region.format(
        id=shard_id, batch=batch))).fetchall()

    areas = set()
    cells = {}
    deleted = 0

    i = 0
    for row in rows:
        code = geocoder.region_for_cell(row.lat, row.lon, row.mcc)
        if code not in cells:
            cells[code] = []
        cells[code].append(row[0])
        if not code:
            # cellid is a 11 byte column, the last 4 byte being the
            # cid, but this is hex encoded, so 22 byte minus 8 byte
            # is the area id
            areas.add(row[0][:14])
            deleted += 1
        i += 1

    for code, cellids in cells.items():
        ids = 'UNHEX("' + '"), UNHEX("'.join(cellids) + '")'
        if not code:
            op.execute(sa.text(stmt_delete_outside.format(
                id=shard_id, ids=ids)))
        else:
            op.execute(sa.text(stmt_update_region.format(
                id=shard_id, code=code, ids=ids)))

    return (i, areas, deleted)


def _upgrade_shard(bind, shard_id, radio, geocoder, circle_radius):
    log.info('Drop cell_%s indices.', shard_id)
    op.execute(sa.text(stmt_drop_index.format(id=shard_id)))

    log.info('Fill cell_%s table.', shard_id)
    op.execute(sa.text(stmt_insert.format(id=shard_id, radio=radio)))

    log.info('Update cell_%s regions.', shard_id)
    length = len(MCC_TO_REGION)
    for i, (mcc, code) in enumerate(MCC_TO_REGION.items()):
        op.execute(sa.text(stmt_update_regions.format(
            id=shard_id, code=code, mcc=mcc)))
        if (i > 0 and i % 50 == 0):
            log.info('Updated %s of %s regions.', i, length)
    log.info('Updated %s of %s regions.', length, length)

    log.info('Add cell_%s indices.', shard_id)
    op.execute(sa.text(stmt_add_index.format(id=shard_id)))

    todo = bind.execute(sa.text(stmt_region_count.format(
        id=shard_id))).fetchone()[0]
    log.info('Updating remaining %s cells.', todo)

    updated_areas = set()
    deleted_total = 0
    updated_total = 0
    while True:
        updated_rows, areas, deleted_rows = _update_region_batch(
            bind, shard_id, geocoder)
        updated_areas = updated_areas.union(areas)
        deleted_total += deleted_rows
        updated_total += updated_rows

        if not updated_rows:
            break
        if ((updated_total and updated_total % 100000 == 0) or
                updated_total == todo):
            log.info('Updated %s of %s cells.', updated_total, todo)

    log.info('Optimize cell_%s table.' % shard_id)
    op.execute(sa.text(stmt_optimize.format(id=shard_id)))

    log.info('Updating %s areas.', len(updated_areas))
    for areaid in updated_areas:
        _update_area(bind, shard_id, areaid, circle_radius)
    log.info('Updated areas.')

    if deleted_total:
        _update_stat(bind, deleted_total)


def upgrade():
    bind = op.get_bind()
    # avoid top-level imports of application code
    from ichnaea.geocalc import circle_radius
    from ichnaea.geocode import GEOCODER

    for shard_id, radio in (('gsm', 0), ('wcdma', 2), ('lte', 3)):
        _upgrade_shard(bind, shard_id, radio, GEOCODER, circle_radius)


def downgrade():
    pass
