"""OpenAI 兼容大模型客户端（DeepSeek / 智谱 / OpenAI / 本地 Ollama 等通用）。"""
import os
import sqlite3
from pathlib import Path
from urllib.parse import urlparse
import json

import httpx


def _load_dotenv() -> None:
    """轻量读取项目根目录 .env（无第三方依赖），不覆盖已有环境变量。"""
    path = Path(__file__).resolve().parents[2] / ".env"
    if not path.is_file():
        return
    try:
        for line in path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            key, value = key.strip(), value.strip().strip('"').strip("'")
            if key and key not in os.environ:
                os.environ[key] = value
    except OSError:
        pass


_load_dotenv()


class LLMError(Exception):
    """大模型调用失败，携带可直接展示给用户的原因。"""


# 环境变量优先于数据库保存的设置（仅当环境变量非空时覆盖）。
# 这样 API Key 可以只放在本机环境变量里，不写入 data/chatbot.db。
ENV_OVERRIDES = {
    "api_base_url": "DEEPSEEK_API_BASE_URL",
    "api_key": "DEEPSEEK_API_KEY",
    "api_model": "DEEPSEEK_MODEL",
}


def _value(settings, field: str) -> str:
    env_value = os.environ.get(ENV_OVERRIDES[field], "").strip()
    if env_value:
        return env_value
    try:
        return (settings[field] or "").strip()
    except (KeyError, IndexError, TypeError):
        return ""


def _is_deepseek(url: str) -> bool:
    return "deepseek.com" in urlparse(url).netloc.lower()


async def chat_completion(settings: sqlite3.Row, system_prompt: str,
                          messages: list, timeout: float = 60.0) -> str:
    api_key = _value(settings, "api_key")
    if not api_key:
        raise LLMError("未配置 API Key，请到「设置」填写或设置环境变量 DEEPSEEK_API_KEY")

    base_url = _value(settings, "api_base_url") or "https://api.deepseek.com"
    model = _value(settings, "api_model") or "deepseek-flash"
    url = base_url.rstrip("/") + "/chat/completions"
    payload = {
        "model": model,
        "messages": [{"role": "system", "content": system_prompt}] + messages,
        "temperature": settings["api_temperature"],
    }
    # DeepSeek V4 默认开启思考模式且此时忽略 temperature；客服场景默认关闭，
    # 让设置页的「温度」滑杆生效，同时降低延迟与 token 费用。
    # 如需开启思考模式：设置 DEEPSEEK_THINKING=enabled。
    if _is_deepseek(url):
        thinking = os.environ.get("DEEPSEEK_THINKING", "disabled").strip().lower()
        payload["thinking"] = {"type": "enabled" if thinking == "enabled" else "disabled"}

    headers = {"Authorization": f"Bearer {api_key}"}

    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            resp = await client.post(url, json=payload, headers=headers)
    except httpx.TimeoutException:
        raise LLMError("大模型请求超时，请稍后重试或检查网络")
    except httpx.HTTPError as exc:
        raise LLMError(f"网络错误：{exc}")

    if resp.status_code != 200:
        try:
            detail = resp.json().get("error", {}).get("message", "") or resp.text[:200]
        except Exception:
            detail = resp.text[:200]
        # 不回显 Key；只透传服务端错误文案（DeepSeek 会把具体原因放在 message 中）。
        raise LLMError(f"接口返回 {resp.status_code}：{detail}")

    try:
        return resp.json()["choices"][0]["message"]["content"].strip()
    except Exception:
        raise LLMError("接口返回格式异常，请检查 Base URL 是否为 OpenAI 兼容地址")


async def test_connection(settings: sqlite3.Row) -> str:
    return await chat_completion(
        settings,
        "你是连接测试助手，只需原样回复对方要求的内容。",
        [{"role": "user", "content": "请回复：连接成功"}],
        timeout=15,
    )


async def chat_completion_stream(settings: sqlite3.Row, system_prompt: str,
                                 messages: list, timeout: float = 60.0):
    """流式调用 OpenAI 兼容接口，逐段产生文本。失败时抛出 LLMError。"""
    api_key = _value(settings, "api_key")
    if not api_key:
        raise LLMError("未配置 API Key，请到「设置」填写或设置环境变量 DEEPSEEK_API_KEY")

    base_url = _value(settings, "api_base_url") or "https://api.deepseek.com"
    model = _value(settings, "api_model") or "deepseek-flash"
    url = base_url.rstrip("/") + "/chat/completions"
    payload = {
        "model": model,
        "messages": [{"role": "system", "content": system_prompt}] + messages,
        "temperature": settings["api_temperature"],
        "stream": True,
    }
    if _is_deepseek(url):
        thinking = os.environ.get("DEEPSEEK_THINKING", "disabled").strip().lower()
        payload["thinking"] = {"type": "enabled" if thinking == "enabled" else "disabled"}

    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            async with client.stream(
                "POST", url,
                json=payload,
                headers={"Authorization": f"Bearer {api_key}"},
            ) as resp:
                if resp.status_code != 200:
                    data = await resp.aread()
                    try:
                        detail = json.loads(data).get("error", {}).get("message", "") or data.decode("utf-8", "replace")[:200]
                    except Exception:
                        detail = data.decode("utf-8", "replace")[:200]
                    raise LLMError(f"接口返回 {resp.status_code}：{detail}")

                async for line in resp.aiter_lines():
                    line = line.strip()
                    if not line or not line.startswith("data:"):
                        continue
                    data = line[5:].strip()
                    if data == "[DONE]":
                        break
                    try:
                        chunk = json.loads(data)
                        content = chunk["choices"][0].get("delta", {}).get("content", "")
                    except Exception:
                        continue
                    if content:
                        yield content
    except LLMError:
        raise
    except httpx.TimeoutException:
        raise LLMError("大模型请求超时，请稍后重试或检查网络")
    except httpx.HTTPError as exc:
        raise LLMError(f"网络错误：{exc}")
