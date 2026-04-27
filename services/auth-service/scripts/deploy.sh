#!/bin/bash
set -e

echo "Starting Owner 1 deployment..."

if [ ! -d "venv" ]; then
  python3 -m venv venv
fi

source venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt

docker compose up -d

echo "Waiting for MySQL to come up..."
sleep 15

echo "Starting app..."
nohup uvicorn app.main:app --host 0.0.0.0 --port 8000 > app.log 2>&1 &

echo "Deployment finished."
echo "Health check: curl http://YOUR_EC2_PUBLIC_IP:8000/health"