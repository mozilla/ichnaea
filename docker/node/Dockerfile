FROM node:6.2.0-slim
MAINTAINER Mozilla Geolocation <dev-geolocation@lists.mozilla.org>

RUN apt-get update && apt-get install -y \
    git \
    && apt-get -y clean \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

CMD ["bash"]

COPY ./package.json /app/package.json
COPY ./npm-shrinkwrap.json /app/npm-shrinkwrap.json

RUN npm install -d /app
RUN npm dedupe
RUN npm shrinkwrap --dev

ENV PATH=$PATH:/app/node_modules/.bin/

COPY ./.bowerrc /app/.bowerrc
COPY ./bower.json /app/bower.json

RUN bower install
