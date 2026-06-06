ARG BUILD_ARCH=aarch64
FROM ghcr.io/home-assistant/${BUILD_ARCH}-base:latest

ARG BUILD_ARCH=aarch64
ARG BUILD_VERSION=0.1.1

LABEL \
    io.hass.version="${BUILD_VERSION}" \
    io.hass.type="app" \
    io.hass.arch="${BUILD_ARCH}" \
    org.opencontainers.image.title="MinuteMetrics" \
    org.opencontainers.image.description="Apple Health exercise-minute competition tracker for Home Assistant" \
    org.opencontainers.image.source="https://github.com/kmcrandom/minutemetrics-ha" \
    org.opencontainers.image.licenses="MIT"

WORKDIR /app

RUN apk add --no-cache python3 py3-pip

COPY requirements.txt /app/requirements.txt
COPY src /app/src
COPY run.sh /run.sh

RUN python3 -m venv /opt/minutemetrics \
    && /opt/minutemetrics/bin/pip install --no-cache-dir --upgrade pip \
    && /opt/minutemetrics/bin/pip install --no-cache-dir -r /app/requirements.txt \
    && chmod a+x /run.sh

ENV MINUTEMETRICS_HOST=0.0.0.0
ENV MINUTEMETRICS_PORT=8080
ENV PATH=/opt/minutemetrics/bin:$PATH

CMD ["/run.sh"]
