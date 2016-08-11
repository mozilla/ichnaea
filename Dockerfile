# mozilla/ichnaea
#
# VERSION 0.1

FROM python:2.7
MAINTAINER dev-geolocation@lists.mozilla.org

WORKDIR /app
EXPOSE 8000

# Open a shell by default.
ENTRYPOINT ["/app/conf/run.sh"]
CMD ["shell"]

RUN groupadd -g 10001 app && \
    useradd -d /app -g 10001 -G app -M -s /bin/sh -u 10001 app

RUN mkdir -p /var/run/location/ && chown -R app:app /var/run/location/

RUN apt-get update && apt-get -y install \
    libgeos-dev \
    libpng12-dev \
    libspatialindex-dev \
    pngquant \
    && rm -rf /var/lib/apt/lists/*

RUN virtualenv --no-site-packages .

COPY docker.make .
RUN make -f docker.make build_deps

COPY ./requirements/*.txt ./requirements/
COPY ./wheelhouse ./wheelhouse
RUN make -f docker.make build_python_deps

COPY . ./
RUN make -f docker.make build_ichnaea

RUN make -f docker.make build_check

RUN chown app:app . && chown -R app:app /app/docs/
VOLUME /app/docs/build/html
USER app
