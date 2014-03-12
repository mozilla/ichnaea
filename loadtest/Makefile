MYSQL_TEST_DB = test_location
MYSQL_USER ?= root
MYSQL_PWD ?= mysql
SQLURI ?= mysql+pymysql://$(MYSQL_USER):$(MYSQL_PWD)@localhost/$(MYSQL_TEST_DB)
SQLSOCKET ?= /opt/local/var/run/mysql56/mysqld.sock

install_fixtures:
	SQLURI=$(SQLURI) SQLSOCKET=$(SQLSOCKET) python install_data.py
