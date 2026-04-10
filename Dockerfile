FROM python:3.10-slim

ARG USER_UID=1000
ARG USER_GID=1000

RUN groupadd -g ${USER_GID} spoolman && \
    useradd -m -u ${USER_UID} -g spoolman spoolman

WORKDIR /app

# Install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy source
COPY spool2klipper.py .
COPY spool2klipper.cfg .

# Setup config directory
RUN mkdir -p /home/spoolman/.config/spool2klipper && \
    cp spool2klipper.cfg /home/spoolman/.config/spool2klipper/ && \
    chown -R spoolman:spoolman /home/spoolman

USER spoolman

ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1

ENTRYPOINT [ "python", "spool2klipper.py" ]
