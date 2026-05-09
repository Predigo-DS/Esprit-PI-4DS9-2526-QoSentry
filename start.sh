#!/bin/bash
set -e

# Grab the LAN IP from the shared mirrored interface
WINDOWS_HOST_IP=$(ip addr show eth1 2>/dev/null | grep 'inet ' | awk '{print $2}' | cut -d/ -f1)

# Fallback to eth0 if eth1 doesn't exist
if [ -z "$WINDOWS_HOST_IP" ]; then
  WINDOWS_HOST_IP=$(ip addr show eth0 2>/dev/null | grep 'inet ' | awk '{print $2}' | cut -d/ -f1)
fi

echo "WINDOWS_HOST_IP=$WINDOWS_HOST_IP" > .env
echo "🪟 Windows/Ollama reachable at: $WINDOWS_HOST_IP"
echo "🚀 Starting stack..."

docker compose up -d
