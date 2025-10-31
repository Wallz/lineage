#!/bin/bash

# Exit on any error
set -e

# Detect Ubuntu version
UBUNTU_VERSION=$(lsb_release -cs)
if [ "$UBUNTU_VERSION" = "focal" ]; then
  DOCKER_COMPOSE="docker-compose"
else
  DOCKER_COMPOSE="docker compose"
fi

echo "=============================="
echo "Starting deployment process"
echo "=============================="

# Pull latest changes from Git
echo "Pulling latest changes from Git..."
git pull origin main || { echo "Failed to pull from Git repository"; exit 1; }

# Activate virtualenv (must exist)
echo "Activating virtual environment..."
source .venv/bin/activate || { echo "Virtualenv not found. Please create it with 'python -m venv .venv'"; exit 1; }

# Upgrade pip
echo "Upgrading pip..."
python -m pip install --upgrade pip || { echo "Failed to upgrade pip"; exit 1; }

# Upgrade installed packages from requirements.txt
echo "Upgrading packages from requirements.txt..."
pip install -U -r requirements.txt || { echo "Failed to upgrade packages"; exit 1; }

# Check Django project for issues
echo "Running Django system check (host)..."
python3 manage.py check || { echo "Django check failed"; exit 1; }

# Create new migrations locally
echo "Making migrations (host)..."
python3 manage.py makemigrations || { echo "Failed to make migrations"; exit 1; }

# Stop running containers
echo "Stopping containers (compose down)..."
$DOCKER_COMPOSE down || { echo "Failed to stop running containers"; }

# Remove legacy/old containers explicitly (compose service names may have changed)
echo "Removing legacy containers..."
legacy_filters=(
  "name=site"           # old app container name (requested)
  "name=site_wsgi"      # new wsgi app container (cleanup previous runs)
  "name=site_http"      # new http app container (cleanup previous runs)
  "name=web"            # common app alias
  "name=django"         # common app alias
  "name=backend"        # common app alias
  "name=celery"
  "name=celery_beat"
  "name=flower"
  "name=nginx"
  "name=redis"
)

containers=$(docker ps -a -q ${legacy_filters[@]})
if [ -n "$containers" ]; then
  docker rm -f $containers || echo "Some legacy containers could not be removed (maybe already removed)"
else
  echo "No legacy containers found to remove."
fi

# Remove optional static_data volume
echo "Removing static_data volume..."
docker volume rm $(docker volume ls -q --filter name=static_data) || echo "Volume not found or already removed"

# Build Docker images
echo "Building Docker images (pulling latest bases)..."
$DOCKER_COMPOSE build --pull || { echo "Failed to build Docker images"; exit 1; }

# Start containers
echo "Starting containers..."
$DOCKER_COMPOSE up -d || { echo "Failed to start containers"; exit 1; }

# Wait for DB (detect common service names)
echo "Waiting for database..."
DB_SERVICE=""
DB_CANDIDATES=("${DB_SERVICE_OVERRIDE}" postgres db postgresql)

for svc in "${DB_CANDIDATES[@]}"; do
  if [ -n "$svc" ]; then
    if $DOCKER_COMPOSE ps --services | grep -q "^${svc}$"; then
      echo "Trying DB service: $svc"
      # Try up to 30s
      for i in {1..15}; do
        if $DOCKER_COMPOSE exec -T "$svc" pg_isready -U "${POSTGRES_USER:-db_user}" > /dev/null 2>&1; then
          DB_SERVICE="$svc"
          break 2
        fi
        echo "$(date '+%H:%M:%S') - $svc not ready yet. Waiting..."
        sleep 2
      done
    fi
  fi
done

if [ -z "$DB_SERVICE" ]; then
  echo "WARNING: Could not detect a PostgreSQL service or it is not responding. Skipping DB wait."
else
  echo "Database service '$DB_SERVICE' is ready."
fi

# Run migration inside container (auto-detect app service)
echo "Applying migrations inside container..."
APP_SERVICE=""
APP_CANDIDATES=("${APP_SERVICE_OVERRIDE}" site_wsgi site_http app web site django backend)
for svc in "${APP_CANDIDATES[@]}"; do
  if [ -n "$svc" ]; then
    if $DOCKER_COMPOSE ps --services | grep -q "^${svc}$"; then
      if $DOCKER_COMPOSE exec -T "$svc" python3 manage.py --version > /dev/null 2>&1; then
        APP_SERVICE="$svc"
        break
      fi
    fi
  fi
done

if [ -z "$APP_SERVICE" ]; then
  echo "ERROR: Could not detect the Django app service to run migrations. Set APP_SERVICE_OVERRIDE or check compose services."
  exit 1
fi

$DOCKER_COMPOSE exec "$APP_SERVICE" python3 manage.py migrate || { echo "Failed to apply migrations"; exit 1; }

# Clean up
echo "Cleaning up..."
docker image prune -f
docker volume prune -f
docker container prune -f
docker builder prune -f

echo "Deployment completed successfully."
