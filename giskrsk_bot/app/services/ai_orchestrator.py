"""AI Copilot Orchestrator — интеллектуальный GIS-ассистент.

Архитектура:
  WebApp/Telegram → AI Orchestrator → Intent Detection
    → Tool Layer (разрешённые GIS-инструменты)
    → Evidence Pack (факты + источники)
    → DeepSeek формирует ответ
    → Пользователь

Принципы:
  - DeepSeek НЕ делает GIS-расчёты (только объясняет)
  - Все геометрические операции — через Shapely/Turf.js/NextGIS API
  - Каждый инструмент возвращает Evidence с источниками
"""

from __future__ import annotations

import json
import logging
from enum import Enum
from typing import Any

from app.core.config import settings
from app.integrations.geoservice import GeoServiceClient
from app.integrations.nextgis import NextGISClient

logger = logging.getLogger(__name__)


# ── Перечисление разрешённых инструментов ──────────────────────
class ToolName(str, Enum):
    GET_PARCEL = "get_parcel"
    FIND_PZZ_ZONE = "find_pzz_zone"
    FIND_INTERSECTIONS = "find_intersections"
    ANALYZE_BUFFER = "analyze_buffer"
    ANALYZE_AREA = "analyze_selected_area"
    SEARCH_DOCUMENTS = "search_documents"
    EXPLAIN_ZONE = "explain_zone"


# ── Evidence Pack (факты с источниками) ─────────────────────────
class EvidencePack:
    """Проверенные факты с указанием источников."""

    def __init__(self) -> None:
        self.facts: list[dict] = []
        self.risks: list[str] = []
        self.missing: list[str] = []
        self.sources: list[dict] = []

    def add_fact(self, label: str, value: Any, source: str, confidence: str = "high") -> None:
        self.facts.append({
            "label": label,
            "value": str(value),
            "source": source,
            "confidence": confidence,
        })

    def add_risk(self, risk: str) -> None:
        self.risks.append(risk)

    def add_missing(self, info: str) -> None:
        self.missing.append(info)

    def add_source(self, name: str, url: str = "") -> None:
        self.sources.append({"name": name, "url": url})

    def to_dict(self) -> dict:
        return {
            "facts": self.facts,
            "risks": self.risks,
            "missing_information": self.missing,
            "sources": self.sources,
        }


# ── Описания инструментов для AI (whitelist) ────────────────────
TOOL_DESCRIPTIONS = {
    ToolName.GET_PARCEL: {
        "description": "Получить информацию об участке по кадастровому номеру",
        "params": {"cadnum": "string (формат XX:XX:XXXXXX:XXX)"},
        "returns": "ObjectInfo: category, permitted_use, area, cadastral_value",
    },
    ToolName.FIND_PZZ_ZONE: {
        "description": "Найти зону ПЗЗ по координатам",
        "params": {"lat": "float", "lon": "float"},
        "returns": "PZZ zone info: zone_code, zone_name, description",
    },
    ToolName.FIND_INTERSECTIONS: {
        "description": "Найти пересечения точки/полигона со слоями (ПЗЗ, ЗОУИТ, красные линии)",
        "params": {"geometry": "GeoJSON", "layers": "list[str]"},
        "returns": "Intersection results per layer",
    },
    ToolName.ANALYZE_BUFFER: {
        "description": "Анализ буфера N метров вокруг точки",
        "params": {"lat": "float", "lon": "float", "meters": "int"},
        "returns": "Objects within buffer zone",
    },
    ToolName.ANALYZE_AREA: {
        "description": "Анализ выделенной области: площадь, покрытие слоями, категории",
        "params": {"polygon": "GeoJSON Polygon"},
        "returns": "Area analysis with layer coverage percentages",
    },
    ToolName.SEARCH_DOCUMENTS: {
        "description": "Поиск в базе документов ПЗЗ по текстовому запросу",
        "params": {"query": "string"},
        "returns": "Document fragments с цитатами",
    },
    ToolName.EXPLAIN_ZONE: {
        "description": "Объяснить зону ПЗЗ: что разрешено, ограничения, параметры",
        "params": {"zone_code": "string (например Ж-1)"},
        "returns": "Explanation with regulations",
    },
}


# ── Orchestrator ────────────────────────────────────────────────
class AiOrchestrator:
    """AI Orchestrator: определяет намерение, выбирает инструменты, собирает Evidence Pack."""

    ALLOWED_TOOLS = {t.value for t in ToolName}

    def __init__(
        self,
        nextgis: NextGISClient | None = None,
        geoservice: GeoServiceClient | None = None,
    ) -> None:
        self.nextgis = nextgis
        self.geoservice = geoservice

    # ── Intent Detection ───────────────────────────────────────
    async def detect_intent(self, user_input: str) -> dict:
        """Определить намерение пользователя через DeepSeek.

        Возвращает: {"intent": "...", "entities": {...}, "tools": [...]}
        """
        if not settings.DEEPSEEK_API_KEY:
            return {"intent": "general", "entities": {}, "tools": []}

        try:
            from openai import AsyncOpenAI

            client = AsyncOpenAI(
                api_key=settings.DEEPSEEK_API_KEY,
                base_url="https://api.deepseek.com/v1",
            )

            system_prompt = """Ты — Intent Router для GIS-ассистента.
Определи намерение пользователя по его сообщению.

Доступные интенты:
- check_parcel: проверка участка по кадастровому номеру
- check_location: проверка зоны ПЗЗ по координатам/адресу
- analyze_area: анализ выделенной области
- search_docs: поиск документов ПЗЗ
- explain_zone: объяснить зону ПЗЗ
- compare: сравнить участки
- buffer: буферный анализ
- general: общий вопрос

Ответь только JSON:
{"intent": "...", "entities": {"cadnum": "...", "lat": ..., "lon": ..., "zone": "..."}, "tools": ["tool1", "tool2"]}
Если данных нет — оставь поля пустыми."""

            resp = await client.chat.completions.create(
                model=settings.DEEPSEEK_MODEL or "deepseek-chat",
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_input},
                ],
                temperature=0.1,
                response_format={"type": "json_object"},
            )

            result = json.loads(resp.choices[0].message.content)
            # Валидация: только разрешённые инструменты
            result["tools"] = [
                t for t in result.get("tools", [])
                if t in self.ALLOWED_TOOLS
            ]
            return result

        except Exception as e:
            logger.error("Intent detection error: %s", e)
            return {"intent": "general", "entities": {}, "tools": []}

    # ── Tool Execution ─────────────────────────────────────────
    async def execute_tool(self, tool_name: str, params: dict) -> EvidencePack:
        """Выполнить разрешённый GIS-инструмент."""
        evidence = EvidencePack()

        try:
            if tool_name == ToolName.GET_PARCEL.value and self.nextgis:
                cadnum = params.get("cadnum", "")
                data = await self.nextgis.search_by_cadnum(cadnum)
                if data:
                    evidence.add_fact("Кадастровый номер", cadnum, "NextGIS Web")
                    if hasattr(data, "category"):
                        evidence.add_fact("Категория", data.category, "NextGIS Web")
                    if hasattr(data, "permitted_use"):
                        evidence.add_fact("ВРИ", data.permitted_use, "NextGIS Web")
                    if hasattr(data, "area"):
                        evidence.add_fact("Площадь", f"{data.area} м²", "NextGIS Web")
                    if hasattr(data, "cadastral_value"):
                        evidence.add_fact("Кадастровая стоимость", f"{data.cadastral_value} ₽", "NextGIS Web")
                else:
                    evidence.add_fact("Участок", cadnum, "NextGIS Web")
                    evidence.add_risk("Участок не найден в NextGIS Web")
                    evidence.add_missing("Проверить через ПКК Росреестра")

            elif tool_name == ToolName.FIND_PZZ_ZONE.value and self.geoservice:
                lat = params.get("lat", 0)
                lon = params.get("lon", 0)
                info = await self.geoservice.identify_by_point(lat, lon)
                if info:
                    evidence.add_fact("Тип объекта", info.category or "не определен", "GeoService")
                    evidence.add_fact("Координаты", f"{lat}, {lon}", "запрос пользователя")
                else:
                    evidence.add_fact("Зона не определена", f"по координатам {lat}, {lon}", "GeoService")

            elif tool_name == ToolName.EXPLAIN_ZONE.value:
                zone = params.get("zone_code", "")
                evidence.add_fact("Зона ПЗЗ", zone, "база данных ПЗЗ")
                evidence.add_missing("Полный регламент зоны необходимо проверить в официальном документе ПЗЗ")

            else:
                evidence.add_fact("Инструмент", tool_name, "система")
                evidence.add_missing("Реализация инструмента в разработке")

        except Exception as e:
            logger.error("Tool %s error: %s", tool_name, e)
            evidence.add_risk(f"Ошибка выполнения: {str(e)}")

        return evidence

    # ── Main pipeline ──────────────────────────────────────────
    async def process_query(
        self,
        user_input: str,
        context: dict | None = None,
    ) -> dict:
        """Полный конвейер: Intent → Tools → Evidence → DeepSeek Ответ."""
        # 1. Определяем намерение
        intent = await self.detect_intent(user_input)

        # 2. Собираем доказательства через инструменты
        combined = EvidencePack()

        # Добавляем контекст если есть (например, клик на карте)
        if context:
            for key, value in context.items():
                combined.add_fact(f"Контекст: {key}", str(value), "карта")

        # Выполняем инструменты
        for tool_name in intent.get("tools", []):
            params = {**intent.get("entities", {}), **(context or {})}
            evidence = await self.execute_tool(tool_name, params)
            combined.facts.extend(evidence.facts)
            combined.risks.extend(evidence.risks)
            combined.missing.extend(evidence.missing)
            combined.sources.extend(evidence.sources)

        # 3. DeepSeek формирует ответ (если есть API ключ)
        if settings.DEEPSEEK_API_KEY:
            explanation = await self._generate_explanation(user_input, combined)
        else:
            explanation = "AI-ассистент недоступен (нет API ключа DeepSeek)."

        return {
            "intent": intent.get("intent", "general"),
            "summary": explanation,
            **combined.to_dict(),
            "disclaimer": "Предварительный информационный анализ. "
                          "Для юридически значимых сведений обратитесь в Росреестр.",
            "data_timestamp": "2026-07-25",
        }

    async def _generate_explanation(self, user_input: str, evidence: EvidencePack) -> str:
        """DeepSeek формирует структурированное объяснение на основе фактов."""
        try:
            from openai import AsyncOpenAI

            client = AsyncOpenAI(
                api_key=settings.DEEPSEEK_API_KEY,
                base_url="https://api.deepseek.com/v1",
            )

            facts_text = "\n".join(
                f"- {f['label']}: {f['value']} (источник: {f['source']})"
                for f in evidence.facts
            )
            risks_text = "\n".join(f"- {r}" for r in evidence.risks) or "- Не выявлено"
            missing_text = "\n".join(f"- {m}" for m in evidence.missing) or "- Нет"

            system_prompt = """Ты — GIS-ассистент для проверки земельных участков.
Формируй ответ на основе ТОЛЬКО предоставленных фактов.
Не выдумывай данные. Если данных нет — напиши "не указано".
Формат: короткий вывод, ключевые факты, ограничения, что проверить дальше.
Не пиши "строить разрешено" — только "по доступным данным объект попадает в зону X". """

            resp = await client.chat.completions.create(
                model=settings.DEEPSEEK_MODEL or "deepseek-chat",
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": f"Вопрос: {user_input}\n\nНайденные факты:\n{facts_text}\n\nОграничения:\n{risks_text}\n\nНеизвестно:\n{missing_text}"},
                ],
                temperature=0.3,
                max_tokens=1000,
            )

            return resp.choices[0].message.content

        except Exception as e:
            logger.error("DeepSeek explanation error: %s", e)
            return "AI-ассистент временно недоступен. Попробуйте позже."
