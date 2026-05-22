"""Unified LLM call service for QA Studio.

All pipeline stages call this single service to interact with LLMs.
Uses httpx to make direct HTTP calls to OpenAI-compatible endpoints,
which works with Aliyun Dashscope and any other OpenAI-compatible provider.

Key design:
- Async entry points: call_llm() / call_llm_json() for use in async contexts
- Sync entry points: call_llm_sync() / call_llm_json_sync() for thread pool workers
- Shared internal helpers: _build_llm_request(), _parse_llm_response(), _handle_llm_error()
- Per-call overrides for model, api_key, base_url (enables per-stage / per-user config)
- Structured output parsing helper: parse_llm_json()
- Full logging for task audit trails
"""

import json
import logging
import re
import time
import traceback
from typing import Tuple

import httpx

from app.config import settings

logger = logging.getLogger("qa_studio.llm")

# ---------------------------------------------------------------------------
# Custom exception
# ---------------------------------------------------------------------------


class LLMCallError(Exception):
    """Raised when an LLM API call fails."""

    def __init__(self, message: str, status_code: int = None, detail: str = None):
        super().__init__(message)
        self.status_code = status_code
        self.detail = detail

    def __str__(self):
        base = super().__str__()
        parts = [base]
        if self.status_code is not None:
            parts.append(f"status={self.status_code}")
        if self.detail:
            parts.append(f"detail={self.detail}")
        return " | ".join(parts)


# ---------------------------------------------------------------------------
# Internal helpers (async/sync shared logic)
# ---------------------------------------------------------------------------


def _build_llm_request(
    prompt: str,
    model: str = None,
    api_key: str = None,
    base_url: str = None,
    system_prompt: str = None,
    temperature: float = 0.7,
    max_tokens: int = 4096,
    base_url_override: str = None,
    api_key_override: str = None,
    model_override: str = None,
    username: str = None,
) -> Tuple[str, dict, dict, str, str]:
    """构建 LLM 请求参数（async/sync 公共逻辑）。

    参数优先级：override > explicit > settings default

    Returns:
        (url, headers, payload, model, user_tag)
    """
    # Resolve effective values: override > explicit > settings default
    model = model_override or model or settings.effective_llm_model
    api_key = api_key_override or api_key or settings.effective_llm_api_key
    base_url = base_url_override or base_url or settings.effective_llm_base_url

    if not api_key:
        raise LLMCallError("LLM API key is not configured", status_code=0)

    # Build the messages payload
    messages = []
    if system_prompt:
        messages.append({"role": "system", "content": system_prompt})
    messages.append({"role": "user", "content": prompt})

    payload = {
        "model": model,
        "messages": messages,
        "temperature": temperature,
        "enable_thinking": False,
    }

    url = f"{base_url.rstrip('/')}/chat/completions"
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }

    user_tag = f"user={username}" if username else ""

    return url, headers, payload, model, user_tag


def _parse_llm_response(
    response_json: dict,
    model: str,
    user_tag: str,
    start_time: float,
    *,
    status_code: int = 200,
    response_text: str = "",
) -> str:
    """解析 LLM 响应（async/sync 公共逻辑）。

    包含状态码检查、content 提取、thinking 标签剥离、空内容检查、日志记录。

    Args:
        response_json: 已解析的响应 JSON dict（response.json() 的结果）
        model: 模型名称（用于日志）
        user_tag: 用户标识（用于日志）
        start_time: 请求开始时间戳
        status_code: HTTP 响应状态码
        response_text: 原始响应文本（非 200 时用于错误详情兜底）

    Returns:
        提取并清理后的 content 文本

    Raises:
        LLMCallError: API 返回错误、响应内容为空、或仅包含思考标签时
    """
    elapsed = time.time() - start_time

    # --- Status code check ---
    if status_code != 200:
        detail = ""
        if response_json:
            detail = response_json.get("error", {}).get("message", str(response_json))
        else:
            detail = response_text[:500] if response_text else ""
        logger.error(
            "LLM call failed | %sstatus=%d | elapsed=%.1fs | detail=%s",
            user_tag + " | " if user_tag else "", status_code, elapsed, detail,
        )
        raise LLMCallError(
            f"LLM API returned status {status_code}",
            status_code=status_code,
            detail=detail,
        )

    # --- Content extraction ---
    content = response_json.get("choices", [{}])[0].get("message", {}).get("content", "")

    if not content:
        logger.error(
            "LLM call returned empty content | %smodel=%s | elapsed=%.1fs | raw_response=%s",
            user_tag + " | " if user_tag else "", model, elapsed,
            json.dumps(response_json, ensure_ascii=False)[:500],
        )
        raise LLMCallError(
            "LLM returned empty response",
            status_code=status_code,
            detail=json.dumps(response_json, ensure_ascii=False)[:500],
        )

    logger.info(
        "LLM call success | %smodel=%s | elapsed=%.1fs | response_len=%d | first_chars=%s",
        user_tag + " | " if user_tag else "", model, elapsed, len(content),
        repr(content[:80]),
    )

    # --- Strip thinking/reasoning blocks from response content ---
    # Handles closed tags: <think>, <thinking>, <reasoning> (case-insensitive)
    original_content = content
    content = re.sub(
        r"<(think|thinking|reasoning)>.*?</\1>", "",
        content, flags=re.DOTALL | re.IGNORECASE,
    )
    # Handles unclosed tags: <think>... (no closing tag, strip to end)
    content = re.sub(
        r"<(think|thinking|reasoning)>.*", "",
        content, flags=re.DOTALL | re.IGNORECASE,
    )
    # Format 2: qwen3 native thinking — uses <tag>...<tag>/AE format
    #   e.g. "xAE\n思考内容\nxAE/AE\n\n实际回复"
    #   Detect tag from first line, find closing marker, strip thinking block.
    stripped = content.strip()
    if stripped:
        first_line = stripped.split('\n')[0].rstrip()
        if first_line and len(first_line) <= 6:
            closing = first_line + "/AE"
            idx = content.find(closing)
            if idx >= 0:
                content = content[idx + len(closing):].strip()

    # 检查剥离思考标签后是否为空（原始内容不为空但剥离后空了 → 模型只返回了思考内容）
    if not content.strip() and original_content.strip():
        logger.error(
            "LLM content became empty after stripping thinking tags | %smodel=%s | original_len=%d | first_chars=%s",
            user_tag + " | " if user_tag else "", model, len(original_content), repr(original_content[:200]),
        )
        raise LLMCallError(
            "LLM response contained only thinking tags, no actual content",
            status_code=200,
            detail=original_content[:500],
        )

    return content


def _handle_llm_error(
    exc: Exception,
    user_tag: str,
    model: str,
    start_time: float,
    timeout: float = None,
):
    """统一处理 LLM 调用异常（async/sync 公共逻辑）。

    处理 timeout、connect error、unexpected error 的日志记录和异常转换。
    Always raises LLMCallError.
    """
    # LLMCallError 已经过处理，直接重新抛出
    if isinstance(exc, LLMCallError):
        raise exc

    elapsed = time.time() - start_time

    if isinstance(exc, httpx.TimeoutException):
        logger.error("LLM call timeout | %selapsed=%.1fs | model=%s",
                     user_tag + " | " if user_tag else "", elapsed, model)
        raise LLMCallError(
            f"LLM call timed out after {timeout}s",
            status_code=0,
        )
    elif isinstance(exc, httpx.ConnectError):
        logger.error(
            "LLM connection error | %selapsed=%.1fs | model=%s | error=%s",
            user_tag + " | " if user_tag else "", elapsed, model, str(exc),
        )
        raise LLMCallError(
            f"Cannot connect to LLM endpoint: {exc}",
            status_code=0,
        )
    else:
        logger.error(
            "LLM call unexpected error | %selapsed=%.1fs | model=%s | error=%s\n%s",
            user_tag + " | " if user_tag else "", elapsed, model, str(exc), traceback.format_exc(),
        )
        raise LLMCallError(
            f"Unexpected LLM call error: {exc}",
            status_code=0,
        )


# ---------------------------------------------------------------------------
# Core LLM call (async)
# ---------------------------------------------------------------------------


async def call_llm(
    prompt: str,
    model: str = None,
    api_key: str = None,
    base_url: str = None,
    system_prompt: str = None,
    temperature: float = 0.7,
    max_tokens: int = 4096,
    timeout: float = 500.0,
    base_url_override: str = None,
    api_key_override: str = None,
    model_override: str = None,
    proxy_override: str = None,
    username: str = None,
) -> str:
    """Call an OpenAI-compatible LLM endpoint and return the text response.

    Args:
        prompt: The user prompt text.
        model: Model name. Defaults to settings.LLM_MODEL.
               Can be overridden by model_override.
        api_key: API key. Defaults to settings.LLM_API_KEY.
                 Can be overridden by api_key_override.
        base_url: Base URL of the OpenAI-compatible endpoint.
                  Defaults to settings.LLM_BASE_URL.
                  Can be overridden by base_url_override.
        system_prompt: Optional system-level instruction.
        temperature: Sampling temperature (0.0 - 2.0).
        max_tokens: Maximum tokens in the response.
        timeout: Request timeout in seconds.
        base_url_override: If provided, takes priority over base_url and settings.
        api_key_override: If provided, takes priority over api_key and settings.
        model_override: If provided, takes priority over model and settings.
        proxy_override: If provided, takes priority over settings.effective_llm_proxy.
        username: Optional username for logging.

    Returns:
        The LLM's text response (content string).

    Raises:
        LLMCallError: On API errors, timeouts, or empty responses.
    """
    url, headers, payload, model, user_tag = _build_llm_request(
        prompt=prompt, model=model, api_key=api_key, base_url=base_url,
        system_prompt=system_prompt, temperature=temperature, max_tokens=max_tokens,
        base_url_override=base_url_override, api_key_override=api_key_override,
        model_override=model_override, username=username,
    )

    start_time = time.time()
    logger.info(
        "LLM call start | %smodel=%s | url=%s | prompt_len=%d",
        user_tag + " | " if user_tag else "", model, url, len(prompt),
    )

    try:
        client_kwargs = {"timeout": timeout}
        effective_proxy = proxy_override or settings.effective_llm_proxy
        if effective_proxy:
            client_kwargs["proxy"] = effective_proxy
        async with httpx.AsyncClient(**client_kwargs) as client:
            response = await client.post(url, json=payload, headers=headers)

        try:
            resp_json = response.json()
        except Exception:
            resp_json = {}

        return _parse_llm_response(
            resp_json, model, user_tag, start_time,
            status_code=response.status_code,
            response_text=response.text[:500] if response.status_code != 200 else "",
        )

    except LLMCallError:
        raise
    except Exception as exc:
        _handle_llm_error(exc, user_tag, model, start_time, timeout)


# ---------------------------------------------------------------------------
# Core LLM call (sync — for thread pool workers)
# ---------------------------------------------------------------------------


def call_llm_sync(
    prompt: str,
    model: str = None,
    api_key: str = None,
    base_url: str = None,
    system_prompt: str = None,
    temperature: float = 0.7,
    max_tokens: int = 4096,
    timeout: float = 500.0,
    base_url_override: str = None,
    api_key_override: str = None,
    model_override: str = None,
    proxy_override: str = None,
    username: str = None,
) -> str:
    """Call an OpenAI-compatible LLM endpoint synchronously.

    Synchronous version of call_llm(), designed for use in thread pool workers.
    Uses httpx.Client instead of httpx.AsyncClient.
    Shares all logic with call_llm() via _build_llm_request() and _parse_llm_response().

    Args:
        Same as call_llm().

    Returns:
        The LLM's text response (content string).

    Raises:
        LLMCallError: On API errors, timeouts, or empty responses.
    """
    url, headers, payload, model, user_tag = _build_llm_request(
        prompt=prompt, model=model, api_key=api_key, base_url=base_url,
        system_prompt=system_prompt, temperature=temperature, max_tokens=max_tokens,
        base_url_override=base_url_override, api_key_override=api_key_override,
        model_override=model_override, username=username,
    )

    start_time = time.time()
    logger.info(
        "LLM call start | %smodel=%s | url=%s | prompt_len=%d",
        user_tag + " | " if user_tag else "", model, url, len(prompt),
    )

    try:
        client_kwargs = {"timeout": timeout}
        effective_proxy = proxy_override or settings.effective_llm_proxy
        if effective_proxy:
            client_kwargs["proxy"] = effective_proxy
        with httpx.Client(**client_kwargs) as client:
            response = client.post(url, json=payload, headers=headers)

        try:
            resp_json = response.json()
        except Exception:
            resp_json = {}

        return _parse_llm_response(
            resp_json, model, user_tag, start_time,
            status_code=response.status_code,
            response_text=response.text[:500] if response.status_code != 200 else "",
        )

    except LLMCallError:
        raise
    except Exception as exc:
        _handle_llm_error(exc, user_tag, model, start_time, timeout)


# ---------------------------------------------------------------------------
# Structured output helper
# ---------------------------------------------------------------------------


def _fix_latex_backslashes(text: str) -> str:
    """Fix unescaped backslashes common in LaTeX from LLMs (e.g. \\alpha → \\\\alpha)."""
    return re.sub(r'\\(?!["\\/bfnrtu])', r'\\\\', text)


def parse_llm_json(text: str) -> dict:
    """Parse a JSON object from LLM response text.

    LLMs sometimes wrap JSON in markdown code blocks or add extra text.
    Some models (e.g. qwen3) also include a <thinking>...</thinking> block
    for reasoning — this is stripped before parsing.

    Args:
        text: Raw LLM response text.

    Returns:
        Parsed dict from the JSON content.

    Raises:
        LLMCallError: If no valid JSON can be extracted.
    """
    # Strip thinking/reasoning blocks before JSON extraction
    # Handles closed tags: <think>, <thinking>, <reasoning> (case-insensitive)
    text = re.sub(
        r"<(think|thinking|reasoning)>.*?</\1>", "",
        text, flags=re.DOTALL | re.IGNORECASE,
    )
    # Handles unclosed tags: <think>... (no closing tag, strip to end)
    text = re.sub(
        r"<(think|thinking|reasoning)>.*", "",
        text, flags=re.DOTALL | re.IGNORECASE,
    )
    # Format 2: qwen3 native thinking — same logic as _parse_llm_response
    stripped = text.strip()
    if stripped:
        first_line = stripped.split('\n')[0].rstrip()
        if first_line and len(first_line) <= 6:
            closing = first_line + "/AE"
            idx = text.find(closing)
            if idx >= 0:
                text = text[idx + len(closing):].strip()
    text = text.strip()

    # Strategy 1: Try direct parse first
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        try:
            return json.loads(_fix_latex_backslashes(text))
        except json.JSONDecodeError:
            pass

    # Strategy 2: Extract from markdown code block (```json ... ``` or ``` ... ```)
    code_block_pattern = re.compile(
        r"```(?:json)?\s*\n?(.*?)\n?\s*```", re.DOTALL
    )
    match = code_block_pattern.search(text)
    if match:
        content = match.group(1).strip()
        try:
            return json.loads(content)
        except json.JSONDecodeError:
            try:
                return json.loads(_fix_latex_backslashes(content))
            except json.JSONDecodeError:
                pass

    # Strategy 3: Find the outermost curly-brace block
    brace_pattern = re.compile(r"\{.*\}", re.DOTALL)
    match = brace_pattern.search(text)
    if match:
        candidate = match.group(0)
        # Try progressively wider matches (innermost braces first)
        for start_pos in range(len(candidate)):
            if candidate[start_pos] != "{":
                continue
            for end_pos in range(len(candidate), start_pos + 1, -1):
                sub = candidate[start_pos:end_pos]
                try:
                    parsed = json.loads(sub)
                    # Only accept if it looks like a meaningful object (at least 1 key)
                    if isinstance(parsed, dict) and len(parsed) > 0:
                        return parsed
                except json.JSONDecodeError:
                    continue

    raise LLMCallError(
        f"Cannot parse JSON from LLM response. Raw text (first 200 chars): {text[:200]}"
    )


# ---------------------------------------------------------------------------
# Convenience: call with JSON output request (async)
# ---------------------------------------------------------------------------


async def call_llm_json(
    prompt: str,
    model: str = None,
    api_key: str = None,
    base_url: str = None,
    system_prompt: str = None,
    temperature: float = 0.3,
    max_tokens: int = 4096,
    timeout: float = 500.0,
    base_url_override: str = None,
    api_key_override: str = None,
    model_override: str = None,
    username: str = None,
) -> dict:
    """Call LLM and parse the response as JSON.

    Uses a lower default temperature (0.3) for more deterministic outputs.
    Automatically adds a system instruction requesting JSON format.
    Falls back to parse_llm_json() for extraction if the response is not pure JSON.

    Args:
        Same as call_llm(), plus defaults adjusted for structured output.
        Override parameters (base_url_override, api_key_override, model_override)
        are passed through to call_llm() and take priority over explicit values.

    Returns:
        Parsed dict from the LLM's JSON response.

    Raises:
        LLMCallError: On API errors or JSON parsing failures.
    """
    # Augment system prompt to request JSON output
    json_instruction = "You must respond with valid JSON only. Do not include any text outside the JSON object."
    if system_prompt:
        effective_system = f"{system_prompt}\n{json_instruction}"
    else:
        effective_system = json_instruction

    raw = await call_llm(
        prompt=prompt,
        model=model,
        api_key=api_key,
        base_url=base_url,
        system_prompt=effective_system,
        temperature=temperature,
        max_tokens=max_tokens,
        timeout=timeout,
        base_url_override=base_url_override,
        api_key_override=api_key_override,
        model_override=model_override,
        username=username,
    )
    return parse_llm_json(raw)


# ---------------------------------------------------------------------------
# Convenience: call with JSON output request (sync — for thread pool workers)
# ---------------------------------------------------------------------------


def call_llm_json_sync(
    prompt: str,
    model: str = None,
    api_key: str = None,
    base_url: str = None,
    system_prompt: str = None,
    temperature: float = 0.3,
    max_tokens: int = 4096,
    timeout: float = 500.0,
    base_url_override: str = None,
    api_key_override: str = None,
    model_override: str = None,
    username: str = None,
) -> dict:
    """Call LLM synchronously and parse the response as JSON.

    Synchronous version of call_llm_json(), designed for use in thread pool workers.

    Args:
        Same as call_llm_json().

    Returns:
        Parsed dict from the LLM's JSON response.

    Raises:
        LLMCallError: On API errors or JSON parsing failures.
    """
    # Augment system prompt to request JSON output
    json_instruction = "You must respond with valid JSON only. Do not include any text outside the JSON object."
    if system_prompt:
        effective_system = f"{system_prompt}\n{json_instruction}"
    else:
        effective_system = json_instruction

    raw = call_llm_sync(
        prompt=prompt,
        model=model,
        api_key=api_key,
        base_url=base_url,
        system_prompt=effective_system,
        temperature=temperature,
        max_tokens=max_tokens,
        timeout=timeout,
        base_url_override=base_url_override,
        api_key_override=api_key_override,
        model_override=model_override,
        username=username,
    )
    return parse_llm_json(raw)
