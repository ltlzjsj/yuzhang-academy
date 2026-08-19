#!/usr/bin/env sh
set -eu

cd "$(dirname "$0")"

if [ ! -f backend.env ]; then
  cp backend.env.example backend.env
  echo "Created deploy/tencent/backend.env. Edit it and set MINIMAX_API_KEY/JWT_SECRET first."
  exit 1
fi

if [ ! -f deploy.env ]; then
  cp deploy.env.example deploy.env
  echo "Created deploy/tencent/deploy.env. Edit MySQL passwords first."
  exit 1
fi

DATA_DIR="$(grep '^DATA_DIR=' deploy.env | head -n 1 | cut -d= -f2-)"
DATA_DIR="${DATA_DIR:-/opt/GeoRag/data}"
mkdir -p "$DATA_DIR/images" "$DATA_DIR/uploads" "$DATA_DIR/mineru_out"

docker compose --env-file deploy.env -f docker-compose.yml up -d --build
