FROM python:3.13-slim

RUN sed -i 's/main/main contrib non-free non-free-firmware/g' /etc/apt/sources.list.d/debian.sources \
    && apt-get update && apt-get install -y \
    iputils-ping \
    telnet \
    curl \
    vim \
    procps \
    snmp \
    snmp-mibs-downloader \
    && rm -rf /var/lib/apt/lists/*

RUN useradd -u 10001 -m -s /bin/bash pdu-web

WORKDIR /pdu-web

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY --chown=pdu-web:pdu-web . .

RUN mv PowerNet-MIB.txt /usr/share/snmp/mibs

USER pdu-web

EXPOSE 5000

CMD ["python", "pducontrol-snmp.py"]
