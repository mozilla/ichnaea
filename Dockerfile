FROM python:2.7-slim

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

# Disable installing doc/man/locale files
RUN echo "\
path-exclude=/usr/share/doc/*\n\
path-exclude=/usr/share/man/*\n\
path-exclude=/usr/share/locale/*\n\
" > /etc/dpkg/dpkg.cfg.d/apt-no-docs

# Install apt-installable dependencies.
RUN apt-get update && apt-get -y install \
    file \
    gcc \
    libffi-dev \
    libgeos-dev \
    libpng-dev \
    libspatialindex-dev \
    libssl-dev \
    make \
    pngquant \
    wget \
    && rm -rf /var/lib/apt/lists/*

# Install dependencies.
COPY ./docker.make /app/
RUN make -f docker.make build_deps

# Install Python libraries.
COPY ./requirements/*.txt /app/requirements/
RUN make -f docker.make build_python_deps

# Install the application code.
COPY . /app
RUN make -f docker.make build_ichnaea

# Run a couple checks to see if things got installed correctly.
RUN make -f docker.make build_check

# The app user only needs write access to very few places.
RUN chown app:app . && \
    chown -R app:app /app/docs/ && \
    chown -R app:app /app/ichnaea/ && \
    chown -R app:app /app/conf/

# This volume is only used while building docs and making those
# available in the git repo, so they can be committed.
VOLUME /app/docs/build/html

# This volume is only used in local testing of the datamaps rendering
# functionality.
VOLUME /app/ichnaea/content/static/tiles

# Define the default web server port.
EXPOSE 8000
USER app
