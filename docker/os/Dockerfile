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
    && apt-get -y clean \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /data
RUN git clone --recursive git://github.com/ericfischer/datamaps
WORKDIR /data/datamaps
RUN git checkout 76e620adabbedabd6866b23b30c145b53bae751e
RUN make all
ENV PATH $PATH:/data/datamaps

WORKDIR /data
RUN git clone --recursive git://github.com/maxmind/libmaxminddb
WORKDIR /data/libmaxminddb
RUN git checkout 1.1.1; git submodule update --init --recursive
RUN ./bootstrap; ./configure; make; make install

WORKDIR /data
RUN git clone --recursive git://github.com/pornel/pngquant
WORKDIR /data/pngquant
RUN git checkout 2.5.2
RUN ./configure; make; make install

WORKDIR /data
RUN ldconfig

CMD ["bash"]
