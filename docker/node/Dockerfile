FROM node:16.14.0-slim

# Note: This uses the node user (uid 1000) that comes with the image.

WORKDIR /app

RUN apt-get update && apt-get --no-install-recommends install -y \
    bzip2 \
    make \
    && apt-get -y clean \
    && rm -rf /var/lib/apt/lists/*

RUN mkdir -p /app && mkdir -p /node
RUN chown -R node:node /app && chown -R node:node /node

USER node
WORKDIR /node

CMD ["bash"]

COPY --chown=node:node ./package.json ./npm-shrinkwrap.json /node/
RUN npm install --no-save -d /node
RUN npm dedupe
RUN npm shrinkwrap

ENV PATH=$PATH:/node/node_modules/.bin/

WORKDIR /app
VOLUME /app
