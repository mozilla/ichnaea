# BBOXX Ichnaea


BBOXX Ichnaea is a modified version of Mozilla's [Ichnaea project](https://github.com/mozilla/ichnaea) (ver 2.1.0). The Ichnaea documentation is very detailed and it is recommended to read it. It contains information on the [architecture](https://mozilla.github.io/ichnaea/install/architecture.html) of the Ichnaea server code, as well as [installation](https://mozilla.github.io/ichnaea/install/index.html) ([development](https://mozilla.github.io/ichnaea/install/devel.html) or [production](https://mozilla.github.io/ichnaea/install/deploy.html)) and [debugging](https://mozilla.github.io/ichnaea/install/debug.html) instructions. Find the full docs [here](https://mozilla.github.io/ichnaea/).

If you are simply looking to use the Geolocation API, then the details are [here](https://mozilla.github.io/ichnaea/api/geolocate.html). Please note that the BBOXX Ichnaea instance uses a different URL endpoint.

## API
The BBOXX Ichnaea instance is hosted at http://location.bboxx.co.uk. To make a geolocation request, make a HTTP POST request to http://location.bboxx.co.uk/v1/geolocate?key=API_KEY where API_KEY is the API token that you have been given. For testing purposes, use the "test" API key (http://location.bboxx.co.uk/v1/geolocate?key=test). The payload of the POST should be a JSON file following the [structure](https://mozilla.github.io/ichnaea/api/geolocate.html) defined in the Ichnaea docs.

Here's an example using cURL and a JSON file named `sample_ichnaea.json` in the current working directory
```
curl -d @sample_ichnaea.json -H 'Content-Type: application/json' -i http://location.bboxx.co.uk/v1/geolocate?key=test

```
Depending on the API key used, different fallback methods are used. Some keys will cause requests to be passed through to UnWired Labs in the case where Ichnaea is unable to estimate a location, typically due to insufficient cell tower data in the MySQL database. To test this behaviour, use the "test_unwired" API key, which uses the UnWired Labs fallback.

## Server Features
The BBOXX Ichnaea server has some additional features to the original Ichnaea 2.1.0 release. The aforementioned UnWired Labs fallback support is one of them, but has since been added to Ichnaea 2.2.0 (and in a much better way). 

Another feature is the automatic daily updating of the database to the latest Mozilla Location Services (MLS) [full cell export](https://location.services.mozilla.com/downloads). A bash script downloads the lastest compressed cell export file, decompresses it and proceeds to run a Python script that uploads the data to the MySQL database. The MySQL syntax ensures that data is only either added or updated, records are never deleted. This script ensures that the BBOXX Ichnaea database is up to date with MLS (not completely, due to the initial dataset).

For other features, read the Ichnaea docs.

## Maintenance
It is NOT recommended to attempt to upgrade the BBOXX Ichnaea to newer versions of Ichnaea. Upgrading could delete the entire database. If you are confident with Docker and MySQL, you could backup the database (warning, it contains a LOT of data and will take a lot of time), upgrade Ichnaea, then restore the database.

To SSH into the BBOXX Ichnaea, you will require a .pem file to grant SSH access.
```
ssh -i path/to/ichnaea-server.pem ubuntu@location.bboxx.co.uk
```
The HOME directory contains various Python scripts used in uploading CSV data to the database. These are only needed for CSV upload, they rarely need to be used.
There's a folder named `ichnaea-2.1.0`, which contains the files required by the server and matches the structure of the Ichnaea repository, with an additional folder named `mls-update` and `latlon_test.py` Python script. `latlon_test.py` was used in updating the max/min lat/lon of each record in the database and should not be needed.

`mls-update` contains the scripts and logs used for updating the database to the lastest MLS full cell export. `mysql_mls_gsm.py` is the Python script used and the logs folder contains 2 logs, one containing full debug output and the other containing start/end times. An update takes roughly an hour to 2 hours. Anything under 30 mins is a fail and usually is a result of low disk space. Check `~/ichnaea-2.1.0/mls-update/logs/mls-update-prog.log` for detailed progress information.
The bash executable script is located in `/etc/cron.daily` and is named `MLS-pull`. This gets run daily at 11pm and this (along with the other `cron.daily` scripts) can be changed via `/etc/crontab` if necessary.

To start/stop/restart the server use (inside the ichnaea-2.1.0 folder):
```
sudo ./server start|stop|restart
```
Note: Ichnaea 2.2.0 has renamed the server script to dev.
This will start/stop/restart docker containers and recompile/interpret code. The time taken may change depending on Python packages.

PLEASE NOTE:
NEVER USE `sudo ./server test`. THIS WILL DELETE THE MYSQL DATABASE AND REDIS.

To debug the server, opening a shell inside a docker container helps to identify issues with the database or redis.
```
sudo ./server shell
```
From here follow steps from the [debugging section](https://mozilla.github.io/ichnaea/install/debug.html) of the docs. However, do NOT perform alembic downgrades/upgrades as this will DELETE database data.

To access the MySQL CLI:
```
mysql -h location.bboxx.co.uk -uroot -plocation location
```
It is recommended to not change any of the data inside the database. `SELECT` statements are acceptable to view table data. The only table that may be edited is the `api_key` table, where API keys are managed. `INSERT` may be used to add a new API key, or `UPDATE` may be used to modify an existing key. It is recommended to have MySQL knowledge before attempting to use the database.


## License

``ichnaea`` is offered under the Apache License 2.0.
