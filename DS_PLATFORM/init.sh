#!/bin/bash
set -e

echo "Validating Docker..."
if ! command -v docker &> /dev/null
then
    echo "Docker could not be found, please install it."
    exit 1
fi

echo "Starting Platform Services..."
cd "$(dirname "$0")"

# Start compose
docker compose up -d

echo "Services started. Waiting for Kafka to be ready..."
sleep 10

echo ""
echo "Platform is running!"
echo "Orchestrator: http://localhost:8000"
echo "Frontend: http://localhost:3000"
echo "MinIO Console: http://localhost:9001 (admin/adminpassword)"
