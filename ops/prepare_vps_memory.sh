#!/usr/bin/env bash
# Provision swap for the local image model on small VPS hosts. Run as root.
set -euo pipefail
if [ "$(id -u)" -ne 0 ]; then
    echo 'Run this script as root.' >&2
    exit 1
fi
swap_file=/var/swap/fabricbot.swap
if [ "$(awk '/SwapTotal:/ {print $2}' /proc/meminfo)" -gt 0 ]; then
    echo 'Swap already enabled; no change needed.'
    exit 0
fi
if [ -e "$swap_file" ]; then
    echo "Existing inactive $swap_file requires inspection; refusing to overwrite it." >&2
    exit 1
fi
install -d -m 700 /var/swap
fallocate -l 2G "$swap_file"
chmod 600 "$swap_file"
mkswap "$swap_file"
swapon "$swap_file"
if ! grep -Fq "$swap_file " /etc/fstab; then
    printf '%s none swap sw 0 0\n' "$swap_file" >> /etc/fstab
fi
swapon --show
