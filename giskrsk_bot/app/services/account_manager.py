"""Account Manager — создание/управление пользователями NextGIS Web."""

from __future__ import annotations

import logging
import secrets
import string
from typing import Any

from app.integrations.nextgis import NextGISClient

logger = logging.getLogger(__name__)

# ID групп в NextGIS Web (нужно создать через API)
# По умолчанию: 5 = "authenticated" (все авторизованные)
GROUP_DEFAULT = 5  # authenticated — минимальный доступ

# Группы для тарифов (будут созданы если нет)
GROUP_BASIC = "basic_users"     # пробный доступ
GROUP_PRO = "pro_users"         # полный доступ


def generate_password(length: int = 12) -> str:
    """Сгенерировать случайный пароль."""
    chars = string.ascii_letters + string.digits + "!@#$%"
    return "".join(secrets.choice(chars) for _ in range(length))


class AccountManager:
    """Управление учётными записями NextGIS Web."""

    def __init__(self, nextgis: NextGISClient) -> None:
        self.nextgis = nextgis
        self._groups: dict[str, int] = {}  # keyname -> id

    async def ensure_groups(self) -> dict[str, int]:
        """Создать группы тарифов если их нет. Вернуть {keyname: id}."""
        if self._groups:
            return self._groups

        client = self.nextgis.client
        # Получаем существующие группы
        r = await client.get("/api/component/auth/group/")
        if r.status_code == 200:
            groups = r.json()
            for g in groups:
                if g["keyname"] in (GROUP_BASIC, GROUP_PRO):
                    self._groups[g["keyname"]] = g["id"]

        # Создаём недостающие группы
        for keyname in [GROUP_BASIC, GROUP_PRO]:
            if keyname not in self._groups:
                display = "Basic Users (пробный)" if "basic" in keyname else "Pro Users (полный)"
                try:
                    r = await client.post(
                        "/api/component/auth/group/",
                        json={"keyname": keyname, "display_name": display, "members": []},
                    )
                    if r.status_code == 200:
                        self._groups[keyname] = r.json()["id"]
                        logger.info("Group created: %s (id=%d)", keyname, self._groups[keyname])
                except Exception as e:
                    logger.warning("Failed to create group %s: %s", keyname, e)

        return self._groups

    async def create_user(
        self,
        login: str,
        password: str | None = None,
        display_name: str = "",
        group_keyname: str = GROUP_BASIC,
    ) -> dict[str, Any]:
        """Создать пользователя в NextGIS Web.

        Returns:
            {"id": int, "login": str, "password": str, "group": str}
        """
        if not password:
            password = generate_password()
        if not display_name:
            display_name = login

        groups = await self.ensure_groups()
        group_id = groups.get(group_keyname, GROUP_DEFAULT)

        client = self.nextgis.client
        r = await client.post(
            "/api/component/auth/user/",
            json={
                "keyname": login,
                "display_name": display_name,
                "password": password,
                "member_of": [group_id],
                "disabled": False,
            },
        )

        if r.status_code != 200:
            error_text = r.text[:200]
            logger.error("Failed to create user: %d %s", r.status_code, error_text)
            raise RuntimeError(f"Failed to create user: {error_text}")

        user_id = r.json()["id"]
        logger.info("User created: id=%d, login=%s, group=%s", user_id, login, group_keyname)

        return {
            "id": user_id,
            "login": login,
            "password": password,
            "group": group_keyname,
        }

    async def delete_user(self, user_id: int) -> bool:
        """Удалить пользователя."""
        client = self.nextgis.client
        r = await client.delete(f"/api/component/auth/user/{user_id}")
        if r.status_code == 200:
            logger.info("User deleted: id=%d", user_id)
            return True
        logger.warning("Failed to delete user %d: %d", user_id, r.status_code)
        return False

    async def disable_user(self, user_id: int) -> bool:
        """Заблокировать пользователя (без удаления)."""
        client = self.nextgis.client
        r = await client.put(
            f"/api/component/auth/user/{user_id}",
            json={"disabled": True},
        )
        if r.status_code == 200:
            logger.info("User disabled: id=%d", user_id)
            return True
        logger.warning("Failed to disable user %d: %d", user_id, r.status_code)
        return False

    async def upgrade_user(self, user_id: int, new_group_keyname: str = GROUP_PRO) -> bool:
        """Перевести пользователя на другой тариф (группу)."""
        groups = await self.ensure_groups()
        new_group_id = groups.get(new_group_keyname, GROUP_DEFAULT)

        client = self.nextgis.client
        r = await client.put(
            f"/api/component/auth/user/{user_id}",
            json={"member_of": [new_group_id]},
        )
        if r.status_code == 200:
            logger.info("User upgraded: id=%d -> group=%s", user_id, new_group_keyname)
            return True
        logger.warning("Failed to upgrade user %d: %d", user_id, r.status_code)
        return False
