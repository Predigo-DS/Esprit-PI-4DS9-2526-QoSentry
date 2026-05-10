#!/bin/bash
set -e

# Grab the LAN IP from the shared mirrored interface
WINDOWS_HOST_IP=$(ip addr show eth1 2>/dev/null | grep 'inet ' | awk '{print $2}' | cut -d/ -f1)

# Fallback to eth0 if eth1 doesn't exist
if [ -z "$WINDOWS_HOST_IP" ]; then
  WINDOWS_HOST_IP=$(ip addr show eth0 2>/dev/null | grep 'inet ' | awk '{print $2}' | cut -d/ -f1)
fi

# Last resort: try any non-loopback interface
if [ -z "$WINDOWS_HOST_IP" ]; then
  WINDOWS_HOST_IP=$(ip route get 1.1.1.1 2>/dev/null | awk '/src/{print $7}' | head -1)
fi

if [ -z "$WINDOWS_HOST_IP" ]; then
  echo "⚠️  Could not detect Windows host IP — Ollama/Windows features will use 127.0.0.1"
  WINDOWS_HOST_IP="127.0.0.1"
fi

echo "WINDOWS_HOST_IP=$WINDOWS_HOST_IP" > .env
echo "🪟 Windows/Ollama reachable at: $WINDOWS_HOST_IP"
echo "🚀 Starting stack..."

docker compose up -d
