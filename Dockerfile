# mozilla/ichnaea
#
# VERSION 0.1

FROM python:2.7
MAINTAINER dev-geolocation@lists.mozilla.org

# add a non-privileged user for installing and running
# the application
RUN groupadd -g 10001 app && \
    useradd -d /app -g 10001 -G app -M -s /bin/sh -u 10001 app

WORKDIR /app

# Open a shell by default.
ENTRYPOINT ["/app/conf/run.sh"]
CMD ["shell"]

# Create an app user owned var/run section.
RUN mkdir -p /var/run/location/ && chown -R app:app /var/run/location/

# Install runtime dependencies
RUN apt-get update && apt-get -y install \
    libgeos-dev \
    libpng12-dev \
    libspatialindex-dev \
    pngquant \
    && rm -rf /var/lib/apt/lists/*

# Create a virtualenv, ignoring system packages.
RUN virtualenv --no-site-packages .

# Install C library dependencies unknown to apt-get.
COPY ./docker.make /app/
RUN make -f docker.make build_deps

# Install Python libraries.
COPY ./requirements/*.txt /app/requirements/
COPY ./wheelhouse/* /app/wheelhouse/
RUN make -f docker.make build_python_deps

# Install the application code.
COPY . /app
RUN make -f docker.make build_ichnaea

# Run a couple checks to see if things got installed correctly.
RUN make -f docker.make build_check

# The app user only needs write access to very few places.
RUN chown app:app . && chown -R app:app /app/docs/

# The volume is only used while building docs and making those
# available in the git repo, so they can be committed.
VOLUME /app/docs/build/html

# Define the default web server port.
EXPOSE 8000
USER app
