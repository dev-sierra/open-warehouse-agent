#!/bin/bash
set -euo pipefail

# NVIDIA drivers are already present on the Deep Learning Base AMI -- this
# only needs to install vLLM, pre-download the model weights, and wire up a
# systemd unit so the runtime instance serves automatically on boot.

curl -LsSf https://astral.sh/uv/install.sh | sh
export PATH="$HOME/.local/bin:$PATH"

sudo mkdir -p /opt/vllm
sudo chown "$USER" /opt/vllm
cd /opt/vllm

uv venv
uv pip install vllm

# Qwen2.5-7B-Instruct is public on Hugging Face -- no token needed.
uv run huggingface-cli download Qwen/Qwen2.5-7B-Instruct \
  --local-dir /opt/vllm/models/Qwen2.5-7B-Instruct

sudo tee /etc/systemd/system/vllm.service > /dev/null <<'EOF'
[Unit]
Description=vLLM OpenAI-compatible server
After=network.target

[Service]
Type=simple
WorkingDirectory=/opt/vllm
ExecStart=/opt/vllm/.venv/bin/vllm serve /opt/vllm/models/Qwen2.5-7B-Instruct --served-model-name qwen2.5:7b-instruct --port 8000
Restart=on-failure

[Install]
WantedBy=multi-user.target
EOF

sudo systemctl enable vllm
