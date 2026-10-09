from __future__ import annotations

from typing import Any


PROTOCOLS = {"chat_completions", "responses", "messages"}
DEFAULT_PROTOCOL = "chat_completions"
PROTOCOL_ALIASES = {"response": "responses", "message": "messages", "chat_completion": "chat_completions"}


def normalize_protocol(value: str | None) -> str:
    protocol = (value or DEFAULT_PROTOCOL).strip().lower()
    protocol = PROTOCOL_ALIASES.get(protocol, protocol)
    if protocol not in PROTOCOLS:
        raise ValueError("ONTOLENS_MODEL_PROTOCOL must be chat_completions, responses, or messages")
    return protocol


def build_request(protocol: str, endpoint: str, model: str, token: str,
                  system_prompt: str, user_content: str) -> tuple[str, dict[str, str], dict[str, Any]]:
    protocol = normalize_protocol(protocol)
    if protocol == "chat_completions":
        return (
            endpoint.rstrip("/") + "/chat/completions",
            {"Authorization": "Bearer " + token} if token else {},
            {"model": model, "temperature": 0, "max_tokens": 700,
             "messages": [{"role": "system", "content": system_prompt},
                          {"role": "user", "content": user_content}]},
        )
    if protocol == "responses":
        return (
            endpoint.rstrip("/") + "/responses",
            {"Authorization": "Bearer " + token} if token else {},
            {"model": model, "temperature": 0, "max_output_tokens": 700,
             "input": [
                 {"role": "system", "content": [{"type": "input_text", "text": system_prompt}]},
                 {"role": "user", "content": [{"type": "input_text", "text": user_content}]},
             ]},
        )
    return (
        endpoint.rstrip("/") + "/messages",
        {"x-api-key": token, "anthropic-version": "2023-06-01"} if token else {"anthropic-version": "2023-06-01"},
        {"model": model, "temperature": 0, "max_tokens": 700, "system": system_prompt,
         "messages": [{"role": "user", "content": user_content}]},
    )


def _text_blocks(value: Any) -> str:
    if isinstance(value, str):
        return value
    if not isinstance(value, list):
        return ""
    return "".join(
        item.get("text", "") for item in value
        if isinstance(item, dict) and item.get("type") in {"text", "output_text"}
        and isinstance(item.get("text"), str)
    )


def extract_text(protocol: str, payload: dict[str, Any]) -> str:
    protocol = normalize_protocol(protocol)
    if protocol == "chat_completions":
        choices = payload.get("choices")
        content = choices[0]["message"]["content"] if isinstance(choices, list) and choices else ""
        text = _text_blocks(content)
    elif protocol == "responses":
        text = _text_blocks(payload.get("output_text", ""))
        if not text:
            output = payload.get("output")
            if isinstance(output, list):
                text = _text_blocks([
                    block for item in output if isinstance(item, dict)
                    for block in item.get("content", []) if isinstance(item.get("content"), list)
                ])
    else:
        text = _text_blocks(payload.get("content", ""))
    if not text:
        raise ValueError("model response contains no text")
    return text
