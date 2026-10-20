# ASR + LLM + TTS 模型方案对比

本文对比之前使用的语音链路与当前项目中的配置。

## 方案概览

| 环节 | 之前的方案 | 当前项目配置 |
|---|---|---|
| ASR（语音识别） | sherpa-onnx Streaming Zipformer 中文模型 | OpenAI Whisper `base`，CUDA 推理，默认语言为中文 |
| LLM（对话模型） | 云端 Claude | 当前项目没有配置 LLM |
| TTS（语音合成） | VITS `zh-aishell3 (int8)` | Piper `zh_CN-huayan-medium` |

## 主要区别

### ASR：流式 Zipformer 与 Whisper

之前的 sherpa-onnx Streaming Zipformer 支持在线流式识别，可以在持续接收音频时逐步返回识别结果，适合实时语音交互。

当前项目使用 Whisper `base`。服务的转写接口接收一整个音频文件，再调用模型识别，属于文件式识别流程。Whisper 是多语言、多任务语音模型，也支持语音翻译和语言识别；本项目当前将默认识别语言设为中文。

两者的识别准确率和响应速度不能仅凭模型名称直接判断，需要用同一批音频、相同语言和相似硬件条件进行实测。流式能力方面，当前项目的接口没有实现边录音边返回文字。

### LLM：Claude 与当前项目

之前的链路中，识别结果会交给云端 Claude 生成回复。当前项目只包含 ASR 和 TTS，没有配置 Claude 或其他 LLM，也没有实现“识别文本 → 大模型回复 → 语音播报”的完整对话流程。

### TTS：VITS AISHELL3 与 Piper Huayan

之前使用 VITS `zh-aishell3 (int8)`；当前项目使用 Piper 引擎和 `zh_CN-huayan-medium` 中文音色。两者使用不同的合成引擎和音色模型，因此音色、韵律、发音表现和合成速度都可能不同，具体效果需要试听相同文本比较。

当前项目中的 Piper 模型文件为 `models/zh_CN-huayan-medium.onnx`，配置名称是 `medium`；文件名没有标注 `int8`，因此不能按之前的 int8 配置来描述它。

## 当前项目配置位置

- `compose.yaml`：设置 ASR 模型、设备、语言及 Piper 模型路径。
- `.env` / `.env.example`：当前默认设置为 `ASR_MODEL=base`、`ASR_DEVICE=cuda`、`ASR_LANGUAGE=zh`。
- `app/main.py`：提供音频文件转写和文本转语音接口，没有 LLM 调用。
- `models/zh_CN-huayan-medium.onnx`：当前配置的 Piper 音色模型。

## 总结

之前的方案是“流式 Zipformer 中文识别 + 云端 Claude 对话 + VITS AISHELL3 合成”；当前项目配置是“Whisper base 文件式识别 + Piper Huayan 本地合成”，尚未包含 LLM 对话环节。因此两套方案在实时性、对话能力和合成音色上都有差异。

> 说明：本文根据项目配置整理。项目配置不等于服务当前正在运行；如需确认容器实际加载的模型，请检查运行中的容器状态及 `/health` 接口。
