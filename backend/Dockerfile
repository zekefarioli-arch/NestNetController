FROM python:3.11-slim

WORKDIR /app

# Install iptables
RUN apt-get update && \
    apt-get install -y iptables iproute2 && \
    rm -rf /var/lib/apt/lists/*

# Copy requirements and install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY ./app /app/app
# Remove this line completely - we'll mount config via volume
#COPY ./config /app/config

# Create logs directory
RUN mkdir -p /app/logs

EXPOSE 8003

CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${API_PORT:-8003}"]
