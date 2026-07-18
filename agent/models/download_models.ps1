# Fetches the Kokoro TTS model files (not committed to git - ~120MB).
# Run once from anywhere: powershell -File agent/models/download_models.ps1

$dir = Split-Path -Parent $MyInvocation.MyCommand.Path

Invoke-WebRequest -Uri "https://github.com/thewh1teagle/kokoro-onnx/releases/download/model-files-v1.0/kokoro-v1.0.int8.onnx" -OutFile "$dir\kokoro-v1.0.int8.onnx"
Invoke-WebRequest -Uri "https://github.com/thewh1teagle/kokoro-onnx/releases/download/model-files-v1.0/voices-v1.0.bin" -OutFile "$dir\voices-v1.0.bin"

Write-Output "Kokoro model files downloaded to $dir"
