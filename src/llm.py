"""
llm.py - LLM API wrapper.
Supports Groq and Gemini. Set LLM_PROVIDER in .env.
Includes retry/backoff for transient rate limits and overloaded models.
"""

import json
import os
import time

import requests

PROVIDER = os.getenv("LLM_PROVIDER", "gemini")

GROQ_MODEL = os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile")
GROQ_URL = "https://api.groq.com/openai/v1/chat/completions"

GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")
GEMINI_URL = "https://generativelanguage.googleapis.com/v1beta/models"


def _get_api_key():
    if PROVIDER == "groq":
        key = os.getenv("GROQ_API_KEY")
        if not key:
            raise ValueError("GROQ_API_KEY not set.")
        return key
    key = os.getenv("GEMINI_API_KEY")
    if not key:
        raise ValueError("GEMINI_API_KEY not set.")
    return key


def _call_with_retry(fn, max_retries=3):
    for attempt in range(max_retries + 1):
        try:
            return fn()
        except RuntimeError as e:
            msg = str(e)
            retryable = "429" in msg or "503" in msg or "UNAVAILABLE" in msg
            if retryable and attempt < max_retries:
                wait = 2 ** attempt * 5
                print(f"    ⏳ LLM busy/rate-limited, retrying in {wait}s...")
                time.sleep(wait)
                continue
            raise


def _call_groq(prompt, max_tokens=1024, temperature=0.3):
    key = _get_api_key()

    def fn():
        resp = requests.post(
            GROQ_URL,
            headers={"Content-Type": "application/json", "Authorization": f"Bearer {key}"},
            json={
                "model": GROQ_MODEL,
                "messages": [{"role": "user", "content": prompt}],
                "max_tokens": max_tokens,
                "temperature": temperature,
            },
            timeout=45,
        )
        if resp.status_code != 200:
            raise RuntimeError(f"Groq API error ({resp.status_code}): {resp.text[:500]}")
        text = resp.json()["choices"][0]["message"]["content"]
        if not text:
            raise RuntimeError("Groq returned empty response")
        return text.strip()

    return _call_with_retry(fn)


def _call_gemini(prompt, max_tokens=1024, temperature=0.3):
    key = _get_api_key()
    url = f"{GEMINI_URL}/{GEMINI_MODEL}:generateContent?key={key}"

    def fn():
        resp = requests.post(
            url,
            headers={"Content-Type": "application/json"},
            json={
                "contents": [{"parts": [{"text": prompt}]}],
                "generationConfig": {
                    "maxOutputTokens": max_tokens,
                    "temperature": temperature,
                    "thinkingConfig": {"thinkingBudget": 0},
                },
            },
            timeout=60,
        )
        if resp.status_code != 200:
            raise RuntimeError(f"Gemini API error ({resp.status_code}): {resp.text[:500]}")
        parts = resp.json().get("candidates", [{}])[0].get("content", {}).get("parts", [])
        text = "".join(p["text"] for p in parts if "text" in p and not p.get("thought"))
        if not text:
            raise RuntimeError("Gemini returned empty response")
        return text.strip()

    return _call_with_retry(fn)


def ask_llm(prompt, max_tokens=1024, temperature=0.3):
    if PROVIDER == "groq":
        return _call_groq(prompt, max_tokens, temperature)
    return _call_gemini(prompt, max_tokens, temperature)


def ask_llm_json(prompt, max_tokens=1024, temperature=0.1):
    raw = ask_llm(prompt, max_tokens, temperature)
    cleaned = raw.replace("```json", "").replace("```", "").strip()
    return json.loads(cleaned)
