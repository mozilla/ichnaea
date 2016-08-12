FROM node:6-slim
MAINTAINER Mozilla Geolocation <dev-geolocation@lists.mozilla.org>

# add a non-privileged user for installing and running
# the application
RUN groupadd -g 10001 app && \
    useradd -d /app -g 10001 -G app -M -s /bin/sh -u 10001 app

RUN apt-get update && apt-get install -y \
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
