FROM python:3.14-slim


WORKDIR /app

RUN apt-get update && apt-get install -y \
    libpq-dev \
    default-libmysqlclient-dev \
    pkg-config \
    gcc \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .
