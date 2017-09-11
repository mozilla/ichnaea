import pyximport
import numpy
pyximport.install(setup_args={"include_dirs":numpy.get_include()}, reload_support=True)
import ichnaea.geocalc as geocalc

import pymysql
import csv
import datetime
import struct
import binascii
import time

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
        print("Starting read...")
        # Read a single record
        sql = "SELECT `cellid`, `lat`, `lon`, `radius` FROM `cell_gsm`"
        cursor.execute(sql)
        result = cursor.fetchall()

        rows = 1
        
        print("Read complete!\nStarting write...")
        for row in result:
        	
        	cellid = row['cellid']
        	lat = row['lat']
        	lon = row['lon']
        	radius = row['radius']

        	if radius > 0:
        		max_lat, min_lat, max_lon, min_lon = geocalc.bbox(lat, lon, radius)
        	else:
        		max_lat = lat
        		min_lat = lat
        		max_lon = lon
        		min_lon = lon

        	#print binascii.hexlify(cellid)
        	#print lat, lon, radius
        	#print max_lat, min_lat, max_lon, min_lon
 		
    		sql = "UPDATE `cell_gsm` SET `max_lat`=%s, `min_lat`=%s, `max_lon`=%s, `min_lon`=%s WHERE `cellid`=%s"
    		cursor.execute(sql, (max_lat, min_lat, max_lon, min_lon, cellid))

    		print("%s/%s complete!" % (rows, len(result)))

        	rows += 1

        connection.commit()

finally:
    connection.close()
    finish = time.strftime("%Y-%m-%d %H:%M") 
    print("Complete! " + finish)





