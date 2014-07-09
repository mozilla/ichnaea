MYSQL_TEST_DB = location
MYSQL_USER ?= location
MYSQL_PWD ?= location
SQLURI ?= mysql+pymysql://$(MYSQL_USER):$(MYSQL_PWD)@$(MYSQL_HOST)/$(MYSQL_TEST_DB)

install_fixtures:
	SQLURI=$(SQLURI) python install_data.py

ipython:
	SQLURI=$(SQLURI) ipython

mysql:
	mysql -u$(MYSQL_USER) --password=$(MYSQL_PWD) -h $(MYSQL_HOST) $(MYSQL_TEST_DB)

submit_cell:
	loads-runner --config submit_cell.ini

submit_wifi:
	loads-runner --config submit_wifi.ini

query_cell:
	loads-runner --config query_cell.ini

query_cell_mixed:
	loads-runner --config query_cell_mixed.ini

query_wifi:
	loads-runner --config query_wifi.ini
