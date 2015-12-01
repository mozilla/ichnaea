FROM mozilla-ichnaea/os
MAINTAINER Mozilla Geolocation <dev-geolocation@lists.mozilla.org>
ENV PYTHONUNBUFFERED 1

WORKDIR /data/ichnaea
RUN virtualenv .
COPY prod-slow.txt requirements/prod-slow.txt
RUN bin/pip install --no-cache-dir --no-deps --disable-pip-version-check \
    -r requirements/prod-slow.txt

WORKDIR /data/ichnaea
COPY package.json npm-shrinkwrap.json ./
RUN npm install -d $(pwd); npm dedupe; npm shrinkwrap --dev

ENV PATH $PATH:/data/ichnaea/node_modules/.bin/
COPY bower.json .bowerrc ./
RUN bower --allow-root install

CMD ["bash"]
