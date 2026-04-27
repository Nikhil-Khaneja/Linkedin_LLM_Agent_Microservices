FROM python:3.11-slim

WORKDIR /app

RUN apt-get update && apt-get install -y gcc default-libmysqlclient-dev pkg-config \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app/ ./app/

EXPOSE 8001

HEALTHCHECK --interval=20s --timeout=10s --retries=5 --start-period=30s \
  CMD python -c "import httpx; r=httpx.get('http://localhost:8001/health',timeout=5); exit(0 if r.status_code==200 else 1)"

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8001", "--workers", "2"]
