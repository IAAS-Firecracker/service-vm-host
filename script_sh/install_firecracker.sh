#!/bin/bash

# Get architecture
ARCH="$(uname -m)"

# Download latest firecracker binary
release_url="https://github.com/firecracker-microvm/firecracker/releases"
latest=$(basename $(curl -fsSLI -o /dev/null -w %{url_effective} ${release_url}/latest))
curl -L ${release_url}/download/${latest}/firecracker-${latest}-${ARCH}.tgz \
| tar -xz

# Move binary to system path
sudo mv release-${latest}-${ARCH}/firecracker-${latest}-${ARCH} /usr/local/bin/firecracker
sudo chmod +x /usr/local/bin/firecracker

# Create necessary directories
sudo mkdir -p /opt/firecracker
sudo chown -R $USER:$USER /opt/firecracker
