#!/usr/bin/env bash
# One-time server setup for the test stand (Ubuntu/Debian).
# Run as root on a fresh VPS. Do NOT commit passwords; use SSH keys only.
#
# Usage:
#   sudo bash scripts/bootstrap-test-stand-ubuntu.sh deployer
#
# After this:
# 1) Copy your GitHub Actions deploy public key to /home/<user>/.ssh/authorized_keys
# 2) Copy embedding artifacts to /opt/visual-model-models/ (logos_embedding.pt + .csv)
# 3) Open TCP 22 (SSH) and the backend port (default 8000) in the firewall / cloud SG

set -euo pipefail

DEPLOY_USER="${1:-deployer}"

if [[ "$(id -u)" -ne 0 ]]; then
  echo "Run as root (sudo)." >&2
  exit 1
fi

apt-get update -y
apt-get install -y ca-certificates curl gnupg rsync

if ! getent passwd "$DEPLOY_USER" >/dev/null; then
  useradd -m -s /bin/bash "$DEPLOY_USER"
fi

install -d -m 700 "/home/$DEPLOY_USER/.ssh"
chown -R "$DEPLOY_USER:$DEPLOY_USER" "/home/$DEPLOY_USER/.ssh"

# Docker Engine (official convenience script — review for your org if needed)
if ! command -v docker >/dev/null 2>&1; then
  curl -fsSL https://get.docker.com | sh
fi

systemctl enable --now docker

usermod -aG docker "$DEPLOY_USER"

install -d -m 755 /opt/naming-check-backend
install -d -m 755 /opt/visual-model-models
chown "$DEPLOY_USER:$DEPLOY_USER" /opt/naming-check-backend /opt/visual-model-models

echo
echo "Bootstrap complete."
echo "- Deploy user: $DEPLOY_USER (add SSH key to ~$DEPLOY_USER/.ssh/authorized_keys)"
echo "- Put models in: /opt/visual-model-models/{logos_embedding.pt,logos_embedding.csv}"
echo "- GitHub secrets: TEST_STAND_USER=$DEPLOY_USER, TEST_STAND_VISUAL_MODELS_DIR=/opt/visual-model-models"
