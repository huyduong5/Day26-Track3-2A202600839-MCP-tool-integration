#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PYTHON="${ROOT}/.venv/bin/python"
SERVER="${ROOT}/implementation/mcp_server.py"

if [[ ! -x "${PYTHON}" ]]; then
  PYTHON="$(command -v python3)"
fi

mkdir -p "${ROOT}/.npm-cache"
NPM_CONFIG_CACHE="${ROOT}/.npm-cache" npx -y @modelcontextprotocol/inspector "${PYTHON}" "${SERVER}"
