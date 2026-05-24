#!/bin/bash
set -e

echo "=== Setting up Ollama + DeepSeek ==="

# Install Ollama
if ! command -v ollama &> /dev/null; then
    echo "[1/4] Installing Ollama..."
    curl -fsSL https://ollama.com/install.sh | sh
else
    echo "[1/4] Ollama already installed"
fi

# Start Ollama service
echo "[2/4] Starting Ollama service..."
systemctl enable ollama 2>/dev/null || true
systemctl start ollama 2>/dev/null || (ollama serve &)
sleep 5

# Pull DeepSeek model
echo "[3/4] Pulling DeepSeek-R1 7B model..."
echo "This may take 5-10 minutes depending on connection speed (~4GB download)"
ollama pull deepseek-r1:7b

# Verify
echo "[4/4] Verifying installation..."
ollama list

echo ""
echo "=== Ollama Setup Complete ==="
echo "Model: deepseek-r1:7b"
echo "API: http://localhost:11434"
echo ""
echo "Test with: curl http://localhost:11434/api/generate -d '{\"model\":\"deepseek-r1:7b\",\"prompt\":\"Hello\",\"stream\":false}'"
