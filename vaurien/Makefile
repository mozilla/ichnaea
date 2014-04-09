proxy_mysql:
	vaurien --proxy 0.0.0.0:4404  --backend 0.0.0.0:3306 --protocol mysql

blackout_mysql:
	vaurien --proxy 0.0.0.0:4404  --backend 0.0.0.0:3306 --protocol mysql --behavior 100:blackout

delay_mysql:
	vaurien --proxy 0.0.0.0:4404  --backend 0.0.0.0:3306 --protocol mysql --behavior 5:delay --behavior-delay-sleep 5

hang_mysql:
	vaurien --proxy 0.0.0.0:4404  --backend 0.0.0.0:3306 --protocol mysql --behavior hang

proxy_redis:
	vaurien --proxy 0.0.0.0:9379 --backend 0.0.0.0:6379 --protocol redis

blackout_redis:
	vaurien --proxy 0.0.0.0:9379 --backend 0.0.0.0:6379 --protocol redis --behavior 100:blackout

delay_redis:
	vaurien --proxy 0.0.0.0:9379  --backend 0.0.0.0:6379 --protocol redis --behavior 100:delay --behavior-delay-sleep 1

hang_redis:
	vaurien --proxy 0.0.0.0:9379  --backend 0.0.0.0:6379 --protocol redis --behavior 100:hang
