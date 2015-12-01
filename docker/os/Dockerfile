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

WORKDIR /data
RUN ldconfig

CMD ["bash"]
