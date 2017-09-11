import pyximport
import numpy
pyximport.install(setup_args={"include_dirs":numpy.get_include()}, reload_support=True)
import geocalc
import pymysql
import csv
import datetime
import struct
import binascii
import time
import mobile_codes
import logging

CELLID_STRUCT = struct.Struct('!bHHHI')

def setup_logger(logger_name, log_file, mode='a', level=logging.INFO):
    l = logging.getLogger(logger_name)
    formatter = logging.Formatter('%(message)s')
    fileHandler = logging.FileHandler(log_file, mode)
    fileHandler.setFormatter(formatter)
    streamHandler = logging.StreamHandler()
    streamHandler.setFormatter(formatter)

    l.setLevel(level)
    l.addHandler(fileHandler)
    l.addHandler(streamHandler)    


setup_logger('log1', "/home/ubuntu/ichnaea-2.1.0/mls-update/logs/mls-update.log")
setup_logger('log2', "/home/ubuntu/ichnaea-2.1.0/mls-update/logs/mls-update-prog.log", 'w')
log = logging.getLogger('log1')
proglog = logging.getLogger('log2')

# Connect to the database
connection = pymysql.connect(host='location.bboxx.co.uk',
                             port=3306,
                             user='root',
                             password='location',
                             db='location',
                             charset='utf8mb4',
                             cursorclass=pymysql.cursors.DictCursor)

try:
    with connection.cursor() as cursor:
        
        start = time.strftime("%Y-%m-%d %H:%M") 
        log.info("Started at " + start)
        proglog.info("Started at " + start)
        
        csv_data = csv.DictReader(open('/tmp/MLS.csv'))
        csv_data.next()

        row_no = 1

        for data in csv_data:
            #print data
            
            if(data['radio']=="GSM"):
                created = float(data['created'])
                modified = float(data['updated'])

                for k,v in data.items():            
                    date = datetime.datetime.utcfromtimestamp(created).strftime('%Y-%m-%d %H:%M:%S')
                    data[k] = v.replace(data['created'], date)

                for k,v in data.items():            
                    date = datetime.datetime.utcfromtimestamp(modified).strftime('%Y-%m-%d %H:%M:%S')
                    data[k] = v.replace(data['updated'], date)

                '''for k,v in data.items():
                    data[k] = v.replace(data['radio'], '0')'''
                #print data

                last_seen = datetime.datetime.utcfromtimestamp(modified).strftime('%Y-%m-%d')
                #print last_seen

                code_num = str(data['mcc'])
                code_alpha = mobile_codes.mcc(code_num)
                try:
                    region = code_alpha[0].alpha2               

                except IndexError:
                    region = None
                    print("mcc = %s skipped!" % (code_num))
                #print region

                lat = float(data['lat'])
                lon = float(data['lon'])
                radius = float(data['range'])

                if radius > 0:
                    max_lat, min_lat, max_lon, min_lon = geocalc.bbox(lat, lon, radius)
                else:
                    max_lat = lat
                    min_lat = lat
                    max_lon = lon
                    min_lon = lon

                try:
                    cellid = str(CELLID_STRUCT.pack(0, int(data['mcc']), int(data['net']), int(data['area']), int(data['cell'])))
                    #print binascii.hexlify(cellid)
                    sql = "REPLACE INTO `cell_gsm` (`max_lat`, `min_lat`, `max_lon`, `min_lon`, `lat`, `lon`, `created`, `modified`, `radius`, `region`, `samples`, `last_seen`, `cellid`, `radio`, `mcc`, `mnc`, `lac`, `cid`) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,_binary %s,%s,%s,%s,%s,%s)"
                    cursor.execute(sql, (max_lat, min_lat, max_lon, min_lon, data['lat'], data['lon'], data['created'], data['updated'], data['range'], region, data['samples'], last_seen, cellid, 0, data['mcc'], data['net'], data['area'], data['cell']))
                
                except struct.error:
                    proglog.info("Struct Error: " + data['area'] + "is over 65535!")    


            proglog.info("Row Done! " + str(row_no))
            row_no += 1

        # connection is not autocommit by default. So you must commit to save
        # your changes.
        connection.commit()

    '''with connection.cursor() as cursor:
        # Read a single record
        sql = "SHOW TABLES"
        cursor.execute(sql)
        result = cursor.fetchall()
        print(result)'''

finally:
    connection.close()
    finish = time.strftime("%Y-%m-%d %H:%M") 
    log.info("Completed at " + finish)
    proglog.info("Completed at " + finish)
