FROM python:3.11-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends curl && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# OTel 추가 (aws-opentelemetry-distro: X-Ray ID 생성 포함)
RUN pip install --no-cache-dir aws-opentelemetry-distro opentelemetry-exporter-otlp
RUN opentelemetry-bootstrap -a install

COPY . .

EXPOSE 8000

CMD ["opentelemetry-instrument", "uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
