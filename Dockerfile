FROM python:3.11-slim

WORKDIR /app

# Install system dependencies for Scrapling
RUN apt-get update && apt-get install -y \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements and install
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Install Scrapling with fetchers
RUN pip install --no-cache-dir "scrapling[fetchers]" && scrapling install

# Copy server code
COPY server.py .

# Run server
CMD ["python", "server.py"]
