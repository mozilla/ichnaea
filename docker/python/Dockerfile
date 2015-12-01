FROM mozilla-ichnaea/os:latest
MAINTAINER Mozilla Geolocation <dev-geolocation@lists.mozilla.org>
ENV PYTHONUNBUFFERED 1

WORKDIR /data/ichnaea
RUN virtualenv .
COPY prod-slow.txt requirements/prod-slow.txt
RUN bin/pip install --no-cache-dir --no-deps --disable-pip-version-check \
    -r requirements/prod-slow.txt

CMD ["bash"]
