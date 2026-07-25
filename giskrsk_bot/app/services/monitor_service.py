"""Сервис мониторинга изменений ПЗЗ для отслеживаемых участков."""

from __future__ import annotations

import hashlib
import json
import logging

from app.core.config import settings
from app.integrations.nextgis import NextGISClient
from app.repositories.change_event_repo import ChangeEventRepo
from app.repositories.notification_repo import NotificationRepo
from app.repositories.tracked_object_repo import TrackedObjectRepo
from app.repositories.layer_sync_repo import LayerSyncRepo

logger = logging.getLogger(__name__)

PARCELLS_LAYER_KEY = "enriched_parcels"


class MonitorService:
    """Проверка изменений данных ПЗЗ для отслеживаемых участков."""

    def __init__(
        self,
        nextgis: NextGISClient,
        tracked_repo: TrackedObjectRepo,
        change_repo: ChangeEventRepo,
        notif_repo: NotificationRepo,
        layer_sync_repo: LayerSyncRepo,
    ) -> None:
        self.nextgis = nextgis
        self.tracked_repo = tracked_repo
        self.change_repo = change_repo
        self.notif_repo = notif_repo
        self.layer_sync_repo = layer_sync_repo

    def _hash_data(self, data: dict) -> str:
        """Вычислить хэш данных участка для сравнения."""
        normalized = json.dumps(data, sort_keys=True, ensure_ascii=False, default=str)
        return hashlib.md5(normalized.encode()).hexdigest()

    def _detect_changes(self, old: dict | None, new: dict) -> list[dict]:
        """Сравнить старые и новые данные, вернуть список изменений."""
        if not old:
            return [{"field": "data", "old_value": None, "new_value": "initial_data"}]

        changes = []
        tracked_fields = [
            ("zone_code", "Зона ПЗЗ"),
            ("zone_name", "Название зоны"),
            ("vri", "ВРИ"),
            ("cadastral_value", "Кадастровая стоимость"),
            ("area_m2", "Площадь"),
        ]

        for field, label in tracked_fields:
            old_val = old.get(field)
            new_val = new.get(field)
            if old_val != new_val:
                changes.append({
                    "field": field,
                    "label": label,
                    "old_value": old_val,
                    "new_value": new_val,
                })

        return changes

    async def check_layer_updates(self) -> dict:
        """Проверить, обновился ли слой участков в NextGIS Web."""
        sync_state = await self.layer_sync_repo.get(PARCELLS_LAYER_KEY)
        if not sync_state:
            return {"updated": False, "error": "Layer not synced yet"}

        try:
            current_version = await self.nextgis.check_layer_version(sync_state.ngw_resource_id)
        except Exception as e:
            logger.error("Failed to check layer version: %s", e)
            await self.layer_sync_repo.mark_error(PARCELLS_LAYER_KEY)
            return {"updated": False, "error": str(e)}

        if current_version <= sync_state.last_seen_version:
            return {"updated": False, "version": current_version}

        # Есть изменения — проверяем отслеживаемые участки
        await self._check_tracked_objects()
        await self.layer_sync_repo.update_version(PARCELLS_LAYER_KEY, current_version)

        return {"updated": True, "version": current_version}

    async def _check_tracked_objects(self) -> int:
        """Проверить все активные отслеживания. Возвращает количество изменений."""
        tracked = await self.tracked_repo.get_all_active()
        changes_count = 0

        for obj in tracked:
            try:
                data = await self.nextgis.search_by_cadnum(obj.cadastral_number)
                if not data:
                    continue

                fields = data.get("fields") or data.get("properties") or {}
                new_snapshot = {
                    "zone_code": fields.get("zone_code"),
                    "zone_name": fields.get("zone_name"),
                    "vri": fields.get("vri"),
                    "cadastral_value": fields.get("cadastral_value"),
                    "area_m2": fields.get("area_m2"),
                }

                new_hash = self._hash_data(new_snapshot)
                if obj.last_snapshot_hash == new_hash:
                    continue  # без изменений

                # Детектим изменения
                old_payload = obj.last_snapshot_payload or {}
                changes = self._detect_changes(old_payload, new_snapshot)

                if not changes:
                    # Обновляем только хэш
                    await self.tracked_repo.update_snapshot(obj.id, new_hash, new_snapshot)
                    continue

                # Создаём событие изменения
                event_types = []
                for c in changes:
                    if "zone" in c["field"]:
                        event_types.append("pzz_zone_changed")
                    elif "vri" in c["field"]:
                        event_types.append("vri_changed")
                    elif "cadastral" in c["field"]:
                        event_types.append("cad_value_changed")

                event_type = "multiple" if len(set(event_types)) > 1 else (event_types[0] if event_types else "updated")
                old_vals = {c["field"]: c["old_value"] for c in changes}
                new_vals = {c["field"]: c["new_value"] for c in changes}

                change_event = await self.change_repo.create(
                    tracked_object_id=obj.id,
                    event_type=event_type,
                    old_values=old_vals,
                    new_values=new_vals,
                )

                # Создаём уведомление
                changes_text = "\n".join([
                    f"• {c['label']}: {c['old_value']} → {c['new_value']}"
                    for c in changes
                ])
                message = (
                    f"🔔 Изменения по участку {obj.cadastral_number}:\n"
                    f"{changes_text}"
                )

                await self.notif_repo.create(
                    telegram_id=obj.telegram_id,
                    change_event_id=change_event.id,
                    message_text=message,
                )

                # Обновляем слепок
                await self.tracked_repo.update_snapshot(obj.id, new_hash, new_snapshot)
                changes_count += 1
                logger.info("Change detected for %s: %s", obj.cadastral_number, event_type)

            except Exception as e:
                logger.error("Monitor check failed for %s: %s", obj.cadastral_number, e)
                continue

        return changes_count

    async def check_single(self, telegram_id: int, cadastral_number: str) -> dict | None:
        """Проверить конкретный участок по запросу пользователя."""
        try:
            data = await self.nextgis.search_by_cadnum(cadastral_number)
            if not data:
                return None

            fields = data.get("fields") or data.get("properties") or {}
            return {
                "cadastral_number": cadastral_number,
                "zone_code": fields.get("zone_code"),
                "zone_name": fields.get("zone_name"),
                "vri": fields.get("vri"),
                "cadastral_value": fields.get("cadastral_value"),
                "area_m2": fields.get("area_m2"),
            }
        except Exception as e:
            logger.error("Check single failed: %s", e)
            return None
