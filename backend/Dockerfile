FROM python:3.12-slim

# libpcap runtime + build headers for Scapy's raw-socket/packet-parsing bits
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpcap-dev \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt gunicorn

COPY backend/ .

EXPOSE 5000

# Raw sockets (ARP scan, live capture) need root/NET_RAW; the app falls back
# to synthetic mock data without it, so the container works either way.
CMD ["gunicorn", "--bind", "0.0.0.0:5000", "--workers", "2", "app:app"]
