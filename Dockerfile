# SPDX-FileCopyrightText: 2025 Sebastian Andersson <sebastian@bittr.nu>
# SPDX-License-Identifier: GPL-3.0-or-later

# Using 3.10-slim for consistency across your Sanctuary tools
FROM python:3.10-slim

# Make UID and GID configurable to match host permissions
ARG USER_UID=1000
ARG USER_GID=1000

# 1. Create a non-root user and group
RUN groupadd -g ${USER_GID} spoolman && \
    useradd -m -u ${USER_UID} -g spoolman spoolman

WORKDIR /app

# 2. Install dependencies
# We copy requirements first to leverage Docker layer caching
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 3. Copy the source code
COPY spool2klipper.py .
COPY spool2klipper.cfg .

# 4. Pre-seed the configuration directory
# The script expects config in ~/.config/spool2klipper/
RUN mkdir -p /home/spoolman/.config/spool2klipper && \
    cp spool2klipper.cfg /home/spoolman/.config/spool2klipper/ && \
    chown -R spoolman:spoolman /home/spoolman

# 5. Switch to the non-root user
USER spoolman

# Python environment variables for container stability
ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1

# 6. Launch the service
ENTRYPOINT [ "python", "spool2klipper.py" ]
