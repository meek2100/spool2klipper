# SPDX-FileCopyrightText: 2026 Sebastian Andersson <sebastian@bittr.nu>
# SPDX-License-Identifier: GPL-3.0-or-later

FROM python:3.11-slim

ARG USER_UID=1000
ARG USER_GID=1000

# 1. Create a non-root user
RUN groupadd -g ${USER_GID} spoolman && \
    useradd -m -u ${USER_UID} -g spoolman spoolman

WORKDIR /app

# 2. Copy source and install via pyproject.toml
COPY . .
RUN pip install --no-cache-dir .

# 3. Pre-seed a default config if none is mounted
RUN mkdir -p /home/spoolman/.config/spool2klipper && \
    cp spool2klipper.cfg /home/spoolman/.config/spool2klipper/spool2klipper.cfg && \
    chown -R spoolman:spoolman /home/spoolman

USER spoolman

ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1

# Override via environment variables or volume-mount a config file
ENTRYPOINT [ "spool2klipper" ]
