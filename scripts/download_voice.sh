#!/usr/bin/env bash
set -euo pipefail

project_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
model_dir="${project_dir}/models"
voice_base="https://huggingface.co/rhasspy/piper-voices/resolve/v1.0.0/zh/zh_CN/huayan/medium"
voice_name="zh_CN-huayan-medium"

mkdir -p "${model_dir}"
curl -fL --retry 3 "${voice_base}/${voice_name}.onnx" -o "${model_dir}/${voice_name}.onnx"
curl -fL --retry 3 "${voice_base}/${voice_name}.onnx.json" -o "${model_dir}/${voice_name}.onnx.json"

echo "Downloaded ${voice_name} to ${model_dir}"
