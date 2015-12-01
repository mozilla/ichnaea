FROM python:2.7.10
MAINTAINER Mozilla Geolocation <dev-geolocation@lists.mozilla.org>

RUN apt-get update && apt-get install -y \
    automake \
    pkg-config \
    && apt-get -y clean \
    && rm -rf /var/lib/apt/lists/*

RUN apt-get update && apt-get install -y \
    binutils \
    cpp \
    curl \
    gfortran \
    less \
    libatlas-dev \
    libblas-dev \
    libevent-dev \
    libffi-dev \
    libgeos-dev \
    liblapack-dev \
    libpng12-dev \
    libspatialindex-dev \
    libssl-dev \
    vim \
    zip \
    && apt-get -y clean \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /data
RUN wget https://github.com/ericfischer/datamaps/archive/76e620adabbedabd6866b23b30c145b53bae751e.tar.gz \
    -O datamaps.tar.gz
WORKDIR /data/datamaps
RUN tar -xf ../datamaps.tar.gz --strip-components=1
RUN make all
ENV PATH $PATH:/data/datamaps

WORKDIR /data
RUN wget https://github.com/maxmind/libmaxminddb/releases/download/1.1.1/libmaxminddb-1.1.1.tar.gz \
    -O libmaxminddb.tar.gz
WORKDIR /data/libmaxminddb
RUN tar -xf ../libmaxminddb.tar.gz --strip-components=1
RUN ./configure; make; make install

WORKDIR /data
RUN wget https://github.com/pornel/pngquant/archive/2.5.2.tar.gz \
    -O pngquant.tar.gz
WORKDIR /data/pngquant
RUN tar -xf ../pngquant.tar.gz --strip-components=1
RUN ./configure; make; make install

# install current version of node.js/npm based on:
# https://github.com/nodejs/docker-node/blob/master/5.1/Dockerfile

# gpg keys listed at https://github.com/nodejs/node
RUN set -ex \
  && for key in \
    9554F04D7259F04124DE6B476D5A82AC7E37093B \
    94AE36675C464D64BAFA68DD7434390BDBE9B9C5 \
    0034A06D9D9B0064CE8ADF6BF1747F4AD2306D93 \
    FD3A5288F042B6850C66B31F09FE44734EB7990E \
    71DCFD284A79C3B38668286BC97EC7A07EDE3FC1 \
    DD8F2338BAE7501E3DD5AC78C273792F7D83545D \
  ; do \
    gpg --keyserver ha.pool.sks-keyservers.net --recv-keys "$key"; \
  done

ENV NPM_CONFIG_LOGLEVEL warn
ENV NODE_VERSION 5.1.0

WORKDIR /data
RUN curl -SLO "https://nodejs.org/dist/v$NODE_VERSION/node-v$NODE_VERSION-linux-x64.tar.gz" \
  && curl -SLO "https://nodejs.org/dist/v$NODE_VERSION/SHASUMS256.txt.asc" \
  && gpg --verify SHASUMS256.txt.asc \
  && grep " node-v$NODE_VERSION-linux-x64.tar.gz\$" SHASUMS256.txt.asc | sha256sum -c - \
  && tar -xzf "node-v$NODE_VERSION-linux-x64.tar.gz" -C /usr/local --strip-components=1 \
  && rm "node-v$NODE_VERSION-linux-x64.tar.gz" SHASUMS256.txt.asc

WORKDIR /data
RUN ldconfig

CMD ["bash"]
