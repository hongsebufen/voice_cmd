#!/usr/bin/env bash
set -euo pipefail

project_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "${project_dir}"

if ! command -v docker >/dev/null 2>&1; then
    echo "Error: Docker is not installed or is not on PATH." >&2
    exit 1
fi

if ! docker compose version >/dev/null 2>&1; then
    echo "Error: Docker Compose v2 is unavailable. Install or enable the Docker Compose plugin." >&2
    exit 1
fi

voice_model="${project_dir}/models/zh_CN-huayan-medium.onnx"
if [[ ! -f "${voice_model}" ]]; then
    echo "Error: Piper voice model not found: ${voice_model}" >&2
    echo "Download it first with: bash scripts/download_voice.sh" >&2
    exit 1
fi

docker compose up -d --build

echo
echo "ASR + TTS service started. API docs: http://localhost:${HOST_PORT:-8000}/docs"
echo "Follow logs with: docker compose logs -f speech"
