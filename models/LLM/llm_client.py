# llm_client.py
import json
import re
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Callable, Optional

import yaml

# Windows 终端默认 GBK 时，确保中文和 emoji 能正常输出
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")


def load_config() -> dict:
    """加载脚本同目录下的 YAML 配置。"""
    config_path = Path(__file__).with_name("config.yaml")
    if not config_path.exists():
        return {}

    with config_path.open("r", encoding="utf-8") as config_file:
        return yaml.safe_load(config_file) or {}


CONFIG = load_config()
LLM_CONFIG = CONFIG.get("llm", {})
ASSISTANT_CONFIG = CONFIG.get("assistant", {})
ROBOT_CONFIG = CONFIG.get("robot", {})

ANALYZE_URL = str(
    LLM_CONFIG.get("analyze_url", "http://192.168.195.187:8006/analyze")
)
ANALYZE_TIMEOUT_SECONDS = float(LLM_CONFIG.get("timeout_seconds", 15))
WAKE_WORDS = tuple(ASSISTANT_CONFIG.get("wake_words", ["小助手", "机械臂"]))
WAKE_WINDOW_SECONDS = float(ASSISTANT_CONFIG.get("wake_window_seconds", 10))

ANALYZE_INSTRUCTION = (
    "判断机械臂命令，仅输出action字段。"
    "action只能是emergency_stop、home、start_inference、chat。"
    "急停、停止、停下、别动=>emergency_stop；"
    "回正、会正、回证、归位、回零=>home；"
    "开始推理、开始推你、开始推力、启动推理、开始识别=>start_inference；"
    "其他=>chat。"
)


def classify_with_llm(text: str) -> str:
    """调用 /analyze，把有噪声的 ASR 文本限制为固定动作枚举。"""
    body = json.dumps(
        {"text": text, "instruction": ANALYZE_INSTRUCTION},
        ensure_ascii=False,
    ).encode("utf-8")
    request = urllib.request.Request(
        ANALYZE_URL,
        data=body,
        headers={"Content-Type": "application/json; charset=utf-8"},
        method="POST",
    )

    try:
        with urllib.request.urlopen(
            request, timeout=ANALYZE_TIMEOUT_SECONDS
        ) as response:
            payload = json.loads(response.read().decode("utf-8"))

        result = payload.get("result")
        if not isinstance(result, dict):
            raise ValueError("响应缺少 result 对象")

        action = str(result.get("action", "chat"))
        allowed_actions = {"emergency_stop", "home", "start_inference", "chat"}
        if action not in allowed_actions:
            raise ValueError(f"未知动作: {action}")

        model = payload.get("model", "unknown")
        print(f"[意图] {model}: {action}")
        return action
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError, ValueError) as exc:
        print(f"[意图] /analyze 调用失败: {exc}")
        return "unavailable"


# ========== 本地机械臂指令 ==========
# 安全相关动作只走本地白名单，不让 LLM 决定是否执行。
COMMAND_ALIASES = {
    "emergency_stop": ("急停", "紧急停止", "马上停", "立即停止", "停下来"),
    "home": ("回正", "归位", "回到原位"),
    "start_inference": ("开始推理", "启动推理", "开始识别"),
}


def normalize_text(text: str) -> str:
    """去掉 ASR 文本中的常见空白和标点，便于匹配固定指令。"""
    return re.sub(r"[\s，。！？、,.!?;；:：]", "", text).lower()


def send_robot_command(command: str) -> None:
    """
    机械臂硬件接入点。

    开发阶段默认 dry_run，只打印指令。接入串口、CAN、ROS2 或厂商 SDK 后，
    在这里发送命令，并等待板端确认；不要把真实控制逻辑交给 LLM。
    """
    if ROBOT_CONFIG.get("dry_run", True):
        print(f"[机械臂][模拟] 执行命令: {command}")
        return

    raise RuntimeError("尚未配置实际机械臂通信接口，已拒绝执行")


class RobotController:
    """把语音指令转换成确定的机械臂控制调用。"""

    def __init__(self, sender: Callable[[str], None] = send_robot_command):
        self._sender = sender

    def _execute(self, command: str, success_reply: str) -> str:
        try:
            self._sender(command)
            return success_reply
        except Exception as exc:
            print(f"[机械臂] 指令 {command} 发送失败: {exc}")
            return "指令发送失败，请检查机械臂连接。"

    def emergency_stop(self) -> str:
        return self._execute("emergency_stop", "已发送急停指令。")

    def home(self) -> str:
        return self._execute("home", "正在回正。")

    def start_inference(self) -> str:
        return self._execute("start_inference", "已开始推理。")


class VoiceAssistant:
    """唤醒、固定指令路由和普通对话的统一入口。"""

    def __init__(self, controller: Optional[RobotController] = None):
        self.controller = controller or RobotController()
        self.awake_until = 0.0

    def _is_awake(self) -> bool:
        return time.monotonic() < self.awake_until

    @staticmethod
    def _matches(text: str, command: str) -> bool:
        return any(alias in text for alias in COMMAND_ALIASES[command])

    def handle_text(self, text: str) -> Optional[str]:
        """
        处理板端 ASR 输出。

        返回 None 表示未唤醒、忽略该文本；返回字符串表示需要播报的内容。
        """
        normalized = normalize_text(text)
        if not normalized:
            return None

        # 急停始终最高优先级，不要求唤醒，以安全侧误触发为原则。
        if self._matches(normalized, "emergency_stop"):
            self.awake_until = 0.0
            return self.controller.emergency_stop()

        wake_detected = any(normalize_text(word) in normalized for word in WAKE_WORDS)
        if wake_detected:
            self.awake_until = time.monotonic() + WAKE_WINDOW_SECONDS
            for wake_word in WAKE_WORDS:
                normalized = normalized.replace(normalize_text(wake_word), "")

        if not self._is_awake():
            return None

        if not normalized:
            return "我在，请说。"

        # 唤醒后的 ASR 文本交给 /analyze 做语义纠错和受限动作分类。
        action = classify_with_llm(normalized)

        if action == "emergency_stop":
            self.awake_until = 0.0
            return self.controller.emergency_stop()

        if action in {"home", "start_inference"}:
            # 运动/任务命令执行一次后退出唤醒状态，减少连续误操作。
            self.awake_until = 0.0
            if action == "home":
                return self.controller.home()
            return self.controller.start_inference()

        if action == "chat":
            return "我听到了，目前支持急停、回正和开始推理。"

        # 云端不可用时，仅对明确白名单做本地降级判断。
        if self._matches(normalized, "home"):
            self.awake_until = 0.0
            return self.controller.home()
        if self._matches(normalized, "start_inference"):
            self.awake_until = 0.0
            return self.controller.start_inference()

        return "意图服务暂时不可用，请稍后再试。"


# ========== 交互测试（直接运行此文件） ==========
if __name__ == "__main__":
    assistant = VoiceAssistant()
    wake_word_text = "、".join(WAKE_WORDS)
    print(f"语音助手测试已启动，唤醒词：{wake_word_text}")
    print("急停无需唤醒；输入 exit、quit 或 退出可结束。")

    while True:
        try:
            user_input = input("\n识别文本: ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\n测试结束。")
            break

        if user_input.lower() in {"exit", "quit"} or user_input == "退出":
            print("测试结束。")
            break

        if not user_input:
            continue

        result = assistant.handle_text(user_input)
        if result is None:
            print("[忽略] 尚未唤醒。")
        else:
            print(f"助手: {result}")
