"""OpenAI 兼容大模型客户端（智谱 / DeepSeek / OpenAI / 本地 Ollama 等通用）。"""
import httpx
import sqlite3


class LLMError(Exception):
    """大模型调用失败，携带可直接展示给用户的原因。"""


async def chat_completion(settings: sqlite3.Row, system_prompt: str,
                          messages: list, timeout: float = 60.0) -> str:
    if not settings["api_key"]:
        raise LLMError("未配置 API Key，请到「设置」填写后再使用真实大模型模式")

    url = settings["api_base_url"].rstrip("/") + "/chat/completions"
    payload = {
        "model": settings["api_model"],
        "messages": [{"role": "system", "content": system_prompt}] + messages,
        "temperature": settings["api_temperature"],
    }
    headers = {"Authorization": f"Bearer {settings['api_key']}"}

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
