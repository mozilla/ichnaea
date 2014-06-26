# Start vaurien for MySQL with REST API enabled on port 8080
mysql_vaurien:
	vaurien --http --http-port 8080 --proxy 0.0.0.0:4404  --backend 0.0.0.0:3306 --protocol mysql

# Start vaurien for redis with REST API enabled on port 8090
redis_vaurien:
	vaurien --http --http-port 8090 --proxy 0.0.0.0:9379 --backend 0.0.0.0:6379 --protocol redis

# Start the ichnaea server using the vaurien proxy ports for Redis and MySQL
start_ichnaea:
	cd .. && ICHNAEA_CFG=integration_tests/ichnaea.ini ./run_server.sh

# Reset proxy so that it just passes through to mysql
dummy_mysql:
	curl -XPUT -d '{"name": "dummy"}' http://localhost:8080/behavior -H "Content-Type: application/json"

# Reset proxy so that it just passes through to redis
dummy_redis:
	curl -XPUT -d '{"name": "dummy"}' http://localhost:8090/behavior -H "Content-Type: application/json"

# Put mysql into 1 second delay
delay_mysql:
	curl -XPUT -d '{"sleep": 1, "name": "delay"}' http://localhost:8080/behavior -H "Content-Type: application/json"

# Put redis into 1 second delay mode
delay_redis:
	curl -XPUT -d '{"sleep": 1, "name": "delay"}' http://localhost:8090/behavior -H "Content-Type: application/json"

# Put mysql into blackout (read packets, then hang)
blackout_mysql:
	curl -XPUT -d '{"name": "blackout"}' http://localhost:8080/behavior -H "Content-Type: application/json"

# Put redis into blackout (read packets, then hang)
blackout_redis:
	curl -XPUT -d '{"name": "blackout"}' http://localhost:8090/behavior -H "Content-Type: application/json"

run_submit:
	python iclient.py --submit

run_search:
	python iclient.py --search
