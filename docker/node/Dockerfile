FROM node:8-slim

# add a non-privileged user for installing and running
# the application
RUN groupadd -g 10001 app && \
    useradd -d /app -g 10001 -G app -M -s /bin/sh -u 10001 app

RUN apt-get update && apt-get install -y \
    bzip2 \
    git \
    make \
    && apt-get -y clean \
    && rm -rf /var/lib/apt/lists/*

RUN mkdir -p /app && mkdir -p /node
RUN chown -R app:app /app && chown -R app:app /node

USER app
WORKDIR /node

CMD ["bash"]

COPY ./package.json /node/package.json
RUN npm install --no-save -d /node
RUN npm dedupe
RUN npm shrinkwrap

WORKDIR /node/node_modules/mapbox.js
RUN npm install && \
    make

ENV PATH=$PATH:/node/node_modules/.bin/

WORKDIR /app
VOLUME /app
