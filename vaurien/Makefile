chaos_mysql_noop:
	vaurien --proxy 0.0.0.0:4404  --backend 0.0.0.0:3306 --protocol mysql

chaos_mysql:
	vaurien --proxy 0.0.0.0:4404  --backend 0.0.0.0:3306 --protocol mysql --behavior 100:delay --behavior-delay-sleep 1

chaos_redis:
	# add a delay of 1 second on every redis call
	vaurien --proxy 0.0.0.0:9379 --backend 0.0.0.0:6379 --protocol redis --behavior 100:delay --behavior-delay-sleep 1
