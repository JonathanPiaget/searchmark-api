#!/bin/bash
set -e

cd "/home/jopi/searchmark-api"

echo "Pulling the latest changes from git..."
git pull

echo "Deploying services..."
docker compose up -d
