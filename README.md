# Jetson ASR + TTS Docker

一个在 Jetson Thor 上运行的本地语音服务：Whisper 使用 CUDA 做语音识别，Piper 使用中文音色合成 WAV。服务使用 FastAPI，启动后可查看 `/docs`。

## 启动

默认基础镜像是当前设备已有的 `thor-pytorch:2.9.1-cu130-r38.2`。如果换了兼容的 Jetson 镜像，修改 `.env` 里的 `THOR_BASE_IMAGE`。

```bash
cd /home/nvidia/workspace/asr-tts-docker
cp .env.example .env
chmod +x scripts/download_voice.sh
./scripts/download_voice.sh
docker compose up -d --build
```

第一次构建会安装 Python 依赖；第一次 ASR 模型加载时，Whisper 会下载 `.env` 中指定的模型到 `cache/whisper`。服务启动后访问：

- API 文档：`http://localhost:8000/docs`
- 健康状态：`http://localhost:8000/health`

## API 示例

语音识别：

```bash
curl -X POST http://localhost:8000/v1/audio/transcriptions \
  -F 'file=@sample.wav' \
  -F 'language=zh'
```

语音合成：

```bash
curl -X POST http://localhost:8000/v1/audio/speech \
  -H 'Content-Type: application/json' \
  -d '{"input":"你好，语音服务已经启动。"}' \
  --output speech.wav
```

Whisper 模型可在 `.env` 里设置为 `tiny`、`base`、`small`、`medium` 或 `large`。模型越大，识别效果通常越好，也会占用更多内存。Piper 音色文件保存在 `models/`，Whisper 模型缓存保存在 `cache/whisper/`。

## 管理

```bash
docker compose logs -f speech
docker compose down
```
