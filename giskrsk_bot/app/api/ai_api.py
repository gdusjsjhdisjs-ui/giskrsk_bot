"""API: AI Copilot endpoints.

Эндпоинты для AI-ассистента:
- POST /api/ai/chat — задать вопрос про участок/зону/документ
- POST /api/ai/explain-feature — объяснить выбранный объект на карте
- POST /api/ai/analyze-area — анализ выделенной области
"""

from __future__ import annotations

import logging

from fastapi import APIRouter, HTTPException, Request

from app.core.config import settings
from app.db.session import async_session_factory
from app.integrations.geoservice import GeoServiceClient
from app.integrations.nextgis import NextGISClient
from app.services.ai_orchestrator import AiOrchestrator
from app.services.parcel_service import normalize_cadnum

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/ai", tags=["ai"])


def _get_orchestrator(request: Request) -> AiOrchestrator:
    """Получить Orchestrator из app.state (уже инициализирован в lifespan)."""
    services = getattr(request.app.state, "services", {})
    orchestrator = services.get("ai_orchestrator")
    if orchestrator:
        return orchestrator
    # Fallback — создаём новый (если lifespan не отработал)
    return AiOrchestrator(
        nextgis=services.get("nextgis"),
        geoservice=services.get("geoservice"),
    )


@router.post("/chat")
async def ai_chat(request: Request) -> dict:
    """Задать любой вопрос про участок, зону ПЗЗ, документы.

    Body: {"message": "Что можно строить на участке 24:11:0330102:814?", "context": {}}
    """
    body = await request.json()
    user_message = body.get("message", "").strip()
    context = body.get("context", {})

    if not user_message:
        raise HTTPException(status_code=400, detail="Message is required")

    if not settings.DEEPSEEK_API_KEY:
        return {
            "summary": "AI-ассистент недоступен. DeepSeek API ключ не настроен.",
            "intent": "unavailable",
            "facts": [],
            "risks": [],
            "missing_information": ["Настройте DEEPSEEK_API_KEY в .env"],
            "disclaimer": "",
        }

    orchestrator = _get_orchestrator(request)
    result = await orchestrator.process_query(user_message, context)

    return result


@router.post("/explain-feature")
async def ai_explain_feature(request: Request) -> dict:
    """Объяснить выбранный объект на карте.

    Body: {
        "layer": "pzz_krsk",
        "properties": {"zone_code": "Ж-1", "zone_name": "Зона застройки ИЖС"},
        "coordinates": [92.85, 56.01],
        "cadnum": "24:11:0330102:814"
    }
    """
    body = await request.json()
    layer = body.get("layer", "")
    props = body.get("properties", {})
    coords = body.get("coordinates", [])
    cadnum = body.get("cadnum", "")

    if not props and not cadnum:
        raise HTTPException(status_code=400, detail="Properties or cadnum required")

    # Формируем контекст
    context = {
        "layer": layer,
        "coordinates": coords,
        **props,
    }

    # Если есть кадастровый номер — ищем участок
    message_parts = []
    if cadnum:
        normalized = normalize_cadnum(cadnum)
        if normalized:
            message_parts.append(f"Что известно об участке {normalized}?")

    zone = props.get("zone_code") or props.get("zone_code_name", "")
    if zone:
        message_parts.append(f"Что означает зона {zone}?")

    if not message_parts:
        message_parts.append("Что это за объект?")

    orchestrator = _get_orchestrator(request)
    result = await orchestrator.process_query(" ".join(message_parts), context)

    # Добавляем флаг для кнопки "✨ Объяснить" на карте
    result["feature_info"] = {
        "layer": layer,
        "properties": props,
        "cadnum": cadnum,
    }

    return result


@router.post("/analyze-area")
async def ai_analyze_area(request: Request) -> dict:
    """Анализ выделенной области на карте.

    Body: {
        "polygon": {"type": "Polygon", "coordinates": [...]},
        "layers": ["pzz_krsk", "zouit"]
    }
    """
    body = await request.json()
    polygon = body.get("polygon", {})
    layers = body.get("layers", [])

    if not polygon:
        raise HTTPException(status_code=400, detail="Polygon GeoJSON required")

    context = {"selected_area": polygon, "requested_layers": layers}
    user_message = "Проанализируй выбранную область на карте."

    orchestrator = _get_orchestrator(request)
    result = await orchestrator.process_query(user_message, context)

    return result


@router.post("/map-command")
async def ai_map_command(request: Request) -> dict:
    """Преобразовать текст пользователя в команду карты (Технология №3).

    Body: {"message": "Покажи только жилые зоны"}
    Returns: {"command": "filter_layer", "params": {...}} или {"command": null}
    """
    body = await request.json()
    message = body.get("message", "").strip()

    if not message:
        raise HTTPException(status_code=400, detail="Message is required")

    orchestrator = _get_orchestrator(request)
    result = await orchestrator.parse_map_command(message)

    if result is None:
        return {"command": None, "reason": "AI-ассистент недоступен"}

    return result
