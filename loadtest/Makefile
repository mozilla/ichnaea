MYSQL_TEST_DB = location
MYSQL_USER ?= location
MYSQL_PWD ?= location
SQLURI ?= mysql+pymysql://$(MYSQL_USER):$(MYSQL_PWD)@$(MYSQL_HOST)/$(MYSQL_TEST_DB)
SQLSOCKET ?= /opt/local/var/run/mysql56/mysqld.sock

install_fixtures:
	SQLURI=$(SQLURI) SQLSOCKET=$(SQLSOCKET) python install_data.py

ipython:
	SQLURI=$(SQLURI) SQLSOCKET=$(SQLSOCKET) ipython

mysql:
	mysql -u location --password=location -h $(MYSQL_HOST)

submit_cell:
	loads-runner --config submit_cell.ini

query_cell:
	loads-runner --config query_cell.ini

query_cell_mixed:
	loads-runner --config query_cell_mixed.ini

query_wifi:
	loads-runner --config query_wifi.ini
