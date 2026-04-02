FROM python:3.11-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends curl && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
RUN opentelemetry-bootstrap -a install

COPY . .

# 진단: opentelemetry-instrument 바이너리 타입 확인 (빌드 로그에서 확인)
RUN apt-get update && apt-get install -y --no-install-recommends file && rm -rf /var/lib/apt/lists/* \
  && file /usr/local/bin/opentelemetry-instrument \
  && head -3 /usr/local/bin/opentelemetry-instrument || true

ENV OTEL_EXPORTER_OTLP_PROTOCOL=grpc

EXPOSE 8000

CMD ["opentelemetry-instrument", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]