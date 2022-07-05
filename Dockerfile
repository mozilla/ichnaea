FROM python:3.10.5-slim

# Set up user and group.
ARG groupid=10001
ARG userid=10001

WORKDIR /app
RUN groupadd --gid $groupid app && \
    useradd -g app --uid $userid --shell /usr/sbin/nologin --create-home app

# Set entrypoint for this image. The entrypoint script takes a service
# to run as the first argument. See the script for available arguments.
ENTRYPOINT ["/app/docker/app_entrypoint.sh"]
CMD ["shell"]

# Create an app user owned var/run section.
RUN mkdir -p /var/run/location/ && chown -R app:app /var/run/location/

# Disable installing doc/man/locale files.
RUN echo "\
path-exclude=/usr/share/doc/*\n\
path-exclude=/usr/share/man/*\n\
path-exclude=/usr/share/locale/*\n\
" > /etc/dpkg/dpkg.cfg.d/apt-no-docs

# Install apt-installable dependencies.
RUN apt-get update && \
    apt-get -y install --no-install-recommends \
    file \
    g++ \
    gcc \
    gfortran \
    libatlas-base-dev \
    libffi-dev \
    libgeos-dev \
    liblapack-dev \
    libmariadb-dev \
    libmariadb-dev-compat \
    libpng-dev \
    libprotobuf-dev \
    libspatialindex-dev \
    libssl-dev \
    make \
    mariadb-client \
    pkg-config \
    pngquant \
    protobuf-compiler \
    redis-tools \
    wget \
    && rm -rf /var/lib/apt/lists/*

# Install dependencies.
COPY ./docker.make /app/
COPY ./vendor /app/vendor/
RUN make -f docker.make build_deps

# Install Python libraries.
COPY requirements.txt /app/requirements.txt
RUN make -f docker.make build_python_deps

# Install geocalc.
COPY . /app
RUN make -f docker.make build_geocalc

ENV PYTHONUNBUFFERED 1
ENV PYTHONDONTWRITEBYTECODE 1
ENV PYTHONPATH /app

# Run a couple checks to see if things got installed correctly.
RUN make -f docker.make build_check

# The app user only needs write access to very few places.
RUN chown app:app . && \
    chown -R app:app /app/docs/ && \
    chown -R app:app /app/ichnaea/

# Define the default web server port.
EXPOSE 8000
USER app
