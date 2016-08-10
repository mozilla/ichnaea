FROM node:6.2.0-slim
MAINTAINER Mozilla Geolocation <dev-geolocation@lists.mozilla.org>

RUN apt-get update && apt-get install -y \
    git \
    make \
    && apt-get -y clean \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /node

CMD ["bash"]

COPY ./package.json /node/package.json
COPY ./npm-shrinkwrap.json /node/npm-shrinkwrap.json

RUN npm install -d /node
RUN npm dedupe
RUN npm shrinkwrap --dev

ENV PATH=$PATH:/node/node_modules/.bin/

COPY ./.bowerrc /node/.bowerrc
COPY ./bower.json /node/bower.json

RUN bower install

WORKDIR /app
VOLUME /app
