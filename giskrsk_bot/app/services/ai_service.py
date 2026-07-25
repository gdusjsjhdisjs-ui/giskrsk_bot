"""AI consultant service via DeepSeek API. Explains PZZ data in plain language."""

from __future__ import annotations

import logging
from typing import Any

from app.core.config import settings

logger = logging.getLogger(__name__)


class AiService:
    """AI consultant using DeepSeek (OpenAI-compatible API)."""

    def __init__(self) -> None:
        self._client: Any = None
        self._model: str = settings.DEEPSEEK_MODEL or "deepseek-chat"

    def _get_client(self):
        if self._client is not None:
            return self._client
        try:
            from openai import AsyncOpenAI
            self._client = AsyncOpenAI(
                api_key=settings.DEEPSEEK_API_KEY,
                base_url="https://api.deepseek.com/v1",
            )
            return self._client
        except ImportError:
            logger.warning("openai package not installed")
            return None
        except Exception as e:
            logger.error("AI client init failed: %s", e)
            return None

    @property
    def available(self) -> bool:
        client = self._get_client()
        return client is not None and bool(settings.DEEPSEEK_API_KEY)

    async def explain_parcel(self, parcel_info: dict, user_question: str | None = None) -> str:
        """Answer any question about a parcel / PZZ zone / land use."""
        if not self.available:
            return self._fallback_explain(parcel_info)

        client = self._get_client()
        if not client:
            return self._fallback_explain(parcel_info)

        zone_code = parcel_info.get("zone_code", "—")
        zone_name = parcel_info.get("zone_name", "—")
        vri = parcel_info.get("vri", "—")
        area = parcel_info.get("area_m2", "—")
        cad_value = parcel_info.get("cadastral_value", "—")

        system_prompt = (
            "You are an expert on Russian land law and urban planning (PZZ/ГПЗУ). "
            "Answer in Russian, in a friendly tone like an experienced colleague. "
            "Use emoji naturally. If you know the answer — explain in detail. "
            "If you dont have enough data — say so honestly. "
            "Answer length: from a couple of sentences to a full paragraph, "
            "depending on the complexity of the question."
        )

        has_data = any(v not in (None, "—", "") for v in [zone_code, zone_name, vri, area, cad_value])
        user_prompt = ""
        if has_data:
            user_prompt += (
                f"Parcel data:\n"
                f"- PZZ zone: {zone_code} ({zone_name})\n"
                f"- Permitted use (VRI): {vri}\n"
                f"- Area: {area} m2\n"
                f"- Cadastral value: {cad_value} RUB\n\n"
            )

        if user_question:
            user_prompt += f"Question: {user_question}"
        elif has_data:
            user_prompt += "Explain in simple terms what can be built on this plot and what cannot."
        else:
            user_prompt = "Explain what PZZ zones are and what you can help with."

        try:
            response = await client.chat.completions.create(
                model=self._model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                temperature=0.7,
                max_tokens=500,
            )
            content = self._clean_text(response.choices[0].message.content.strip())
            usage = response.usage
            if usage:
                token_info = (
                    f"\n\n\u2014\n"
                    f"\u2139 Tokens: {usage.prompt_tokens} in + "
                    f"{usage.completion_tokens} out = "
                    f"{usage.total_tokens} total"
                )
                if len(content) + len(token_info) < 4000:
                    content += token_info
            return content

        except Exception as e:
            err = str(e)
            logger.error("DeepSeek error: %s", err)
            if "timeout" in err.lower() or "timed out" in err.lower():
                return "Timeout. Try a shorter question or try again."
            if "rate" in err.lower():
                return "Rate limit hit. Wait a moment and try again."
            return f"Error: {err[:200]}"

    async def generate_geojson(self, coordinates_text: str) -> str:
        """Generate a valid GeoJSON file from coordinate text.

        DeepSeek receives coordinates in any format (EPSG:3857 or EPSG:4326),
        parses them and returns a complete GeoJSON FeatureCollection with a Polygon.
        """
        if not self.available:
            return '{"error": "AI недоступен. Проверьте API-ключ DeepSeek."}'

        client = self._get_client()
        if not client:
            return '{"error": "AI клиент не инициализирован."}'

        system_prompt = (
            "You are a GeoJSON generator. Your ONLY task is to convert "
            "user-provided coordinates into a GeoJSON FeatureCollection "
            "containing a single Polygon feature.\n\n"
            "EXACT OUTPUT FORMAT (copy this structure exactly):\n"
            "{\"type\": \"FeatureCollection\", \"features\": [{\"type\": \"Feature\", \"properties\": {}, \"geometry\": {\"type\": \"Polygon\", \"coordinates\": [[[lon1, lat1], [lon2, lat2], [lon3, lat3], [lon1, lat1]]]}}]}\n\n"
            "RULES:\n"
            "1. Return ONLY valid JSON — no explanations, no comments, no markdown, no backticks.\n"
            "2. Response must start with { and end with }.\n"
            "3. Coordinates MUST be in EPSG:4326 (longitude, latitude).\n"
            "4. If user sends EPSG:3857 (meters) — CONVERT to EPSG:4326:\n"
            "   lon = x_3857 * 180 / 20037508.34\n"
            "   lat = atan(exp(y_3857 * pi / 20037508.34)) * 360 / pi - 90\n"
            "5. Polygon MUST be CLOSED: first coordinate pair = last coordinate pair.\n"
            "6. Round coordinates to 8 decimal places.\n"
            "7. Use 5+ coordinate pairs minimum for a proper polygon shape.\n"
            "8. If user sends only 2-3 points, generate additional intermediate points to make a proper polygon.\n"
            "9. The output must be parseable by Python json.loads().\n"
            "10. NEVER return error messages or explanations — always return valid GeoJSON."
        )

        user_prompt = (
            f"Convert these coordinates into a GeoJSON Polygon (EPSG:4326).\n\n"
            f"INPUT COORDINATES:\n{coordinates_text}\n\n"
            f"Return ONLY raw JSON FeatureCollection."
        )

        try:
            response = await client.chat.completions.create(
                model=self._model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                temperature=0.1,  # Low temp for deterministic output
                max_tokens=2000,
            )
            content = response.choices[0].message.content.strip()
            # Clean markdown code blocks if model ignores instructions
            content = self._strip_code_blocks(content)
            # Validate it's actually JSON
            try:
                import json
                parsed = json.loads(content)
                # Ensure FeatureCollection
                if parsed.get("type") != "FeatureCollection":
                    # Wrap in FeatureCollection
                    if parsed.get("type") == "Feature":
                        content = json.dumps({
                            "type": "FeatureCollection",
                            "features": [parsed]
                        }, ensure_ascii=False)
                    elif parsed.get("type") == "Polygon":
                        content = json.dumps({
                            "type": "FeatureCollection",
                            "features": [{
                                "type": "Feature",
                                "properties": {},
                                "geometry": parsed
                            }]
                        }, ensure_ascii=False)
            except (json.JSONDecodeError, Exception) as e:
                logger.warning("GeoJSON validation failed: %s", e)
                return f'{{"error": "AI вернул некорректный JSON: {e}"}}'

            return self._clean_text(content)

        except Exception as e:
            err = str(e)
            logger.error("DeepSeek GeoJSON generation error: %s", err)
            if "timeout" in err.lower() or "timed out" in err.lower():
                return '{"error": "Таймаут DeepSeek. Попробуйте ещё раз."}'
            if "rate" in err.lower():
                return '{"error": "Лимит запросов DeepSeek. Подождите и попробуйте снова."}'
            return f'{{"error": "Ошибка AI: {err[:200]}"}}'

    async def batch_summary(self, stats: dict) -> str:
        """Short batch check summary via AI."""
        if not self.available:
            return self._fallback_batch_summary(stats)

        client = self._get_client()
        if not client:
            return self._fallback_batch_summary(stats)

        prompt = (
            f"Batch check results:\n"
            f"- Total: {stats.get('total', 0)}\n"
            f"- Found: {stats.get('ok', 0)}\n"
            f"- Invalid format: {stats.get('invalid_format', 0)}\n"
            f"- Not found: {stats.get('not_found', 0)}\n"
            f"- API errors: {stats.get('api_error', 0)}\n\n"
            f"Give a short summary in Russian (2-3 sentences)."
        )

        try:
            response = await client.chat.completions.create(
                model=self._model,
                messages=[
                    {"role": "system", "content": "You are a geo-analytics assistant. Answer briefly."},
                    {"role": "user", "content": prompt},
                ],
                temperature=0.3,
                max_tokens=300,
            )
            return self._clean_text(response.choices[0].message.content.strip())
        except Exception:
            return self._fallback_batch_summary(stats)

    @staticmethod
    def _strip_code_blocks(text: str) -> str:
        """Remove markdown code block fences from AI output."""
        import re
        # Remove ```json ... ```
        text = re.sub(r'```\w*\n?', '', text)
        # Remove ~~~ ... ~~~
        text = re.sub(r'~~~\w*\n?', '', text)
        return text.strip()

    @staticmethod
    def _clean_text(text: str) -> str:
        """Remove characters that break Telegram's UTF-8 (surrogates, bad controls)."""
        # Filter by character code: keep only valid chars
        return "".join(
            ch for ch in text
            if 0x20 <= ord(ch) <= 0xD7FF or 0xE000 <= ord(ch) <= 0xFFFD
            or ch in "\n\t"
        )

    def _fallback_explain(self, data: dict) -> str:
        zone_code = data.get("zone_code", "?")
        zone_name = data.get("zone_name", "—")
        vri = data.get("vri", "—")
        return self._clean_text(f"Zone {zone_code} - {zone_name}\nVRI: {vri}")

    def _fallback_batch_summary(self, stats: dict) -> str:
        return self._clean_text(
            f"Total: {stats.get('total', 0)}, "
            f"OK: {stats.get('ok', 0)}, "
            f"Errors: {stats.get('errors', 0)}"
        )
