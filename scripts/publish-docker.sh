#!/usr/bin/env bash
set -e

# Change to repository root directory
REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT"

echo "=========================================="
echo " Buddhi AI Studio - Docker Publish Script "
echo "=========================================="

# Check if docker is installed
if ! command -v docker >/dev/null 2>&1; then
  echo "Error: 'docker' command not found. Please install Docker." >&2
  exit 1
fi

# Check if Docker daemon is running
if ! docker info >/dev/null 2>&1; then
  echo "Error: Docker daemon is not running. Please start Docker." >&2
  exit 1
fi

# Determine default version
DETECTED_VERSION=""
if command -v node >/dev/null 2>&1 && [ -f "package.json" ]; then
  DETECTED_VERSION=$(node -p "require('./package.json').version" 2>/dev/null || true)
elif [ -f "package.json" ]; then
  DETECTED_VERSION=$(grep '"version"' package.json | head -n 1 | awk -F '"' '{print $4}' || true)
fi

VERSION="$1"
if [ -z "$VERSION" ]; then
  if [ -n "$DETECTED_VERSION" ]; then
    read -r -p "Enter version tag [default: $DETECTED_VERSION]: " INPUT_VERSION
    VERSION="${INPUT_VERSION:-$DETECTED_VERSION}"
  else
    read -r -p "Enter version tag (e.g. 0.2.0): " VERSION
  fi
fi

if [ -z "$VERSION" ]; then
  echo "Error: Version cannot be empty." >&2
  exit 1
fi

# Strip leading 'v' if provided (e.g., v0.2.0 -> 0.2.0)
VERSION="${VERSION#v}"

BACKEND_IMAGE="buddhilive/ai-studio-service"
FRONTEND_IMAGE="buddhilive/ai-studio-ui"

echo ""
echo "Target Images:"
echo "  Backend:  ${BACKEND_IMAGE}:${VERSION} & ${BACKEND_IMAGE}:latest"
echo "  Frontend: ${FRONTEND_IMAGE}:${VERSION} & ${FRONTEND_IMAGE}:latest"
echo ""

# 1. Build Backend
echo "--> Building Backend image..."
docker build \
  -t "${BACKEND_IMAGE}:${VERSION}" \
  -t "${BACKEND_IMAGE}:latest" \
  -f backend/Dockerfile \
  ./backend

# 2. Build Frontend
echo "--> Building Frontend image..."
docker build \
  -t "${FRONTEND_IMAGE}:${VERSION}" \
  -t "${FRONTEND_IMAGE}:latest" \
  -f Dockerfile \
  .

# 3. Publish Backend
echo "--> Pushing Backend images to Docker Hub..."
docker push "${BACKEND_IMAGE}:${VERSION}"
docker push "${BACKEND_IMAGE}:latest"

# 4. Publish Frontend
echo "--> Pushing Frontend images to Docker Hub..."
docker push "${FRONTEND_IMAGE}:${VERSION}"
docker push "${FRONTEND_IMAGE}:latest"

echo ""
echo "=========================================="
echo " Successfully published Buddhi AI Studio! "
echo "  - ${BACKEND_IMAGE}:${VERSION}"
echo "  - ${BACKEND_IMAGE}:latest"
echo "  - ${FRONTEND_IMAGE}:${VERSION}"
echo "  - ${FRONTEND_IMAGE}:latest"
echo "=========================================="
