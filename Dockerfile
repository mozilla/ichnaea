# mozilla/ichnaea-build
#
# VERSION 0.1

FROM python:2.7
MAINTAINER dev-geolocation@lists.mozilla.org

WORKDIR /app

RUN groupadd -g 10001 app && \
    useradd -d /app -g 10001 -G app -M -s /bin/sh -u 10001 app

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

ENTRYPOINT ["/bin/bash"]

VOLUME /app/docs/build/html
# USER app
