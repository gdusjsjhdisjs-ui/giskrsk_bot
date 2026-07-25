"""Каталог магазина георесурсов.

Здесь перечислены товары, которые продаются в боте.
Чтобы добавить/изменить товар — отредактируйте список SHOP_ITEMS.
Файлы товаров кладите в папку shop_files/ рядом с ботом.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ShopItem:
    id: str
    title: str
    description: str
    price: int  # в рублях
    file_path: str  # путь к файлу, который выдаётся после оплаты


SHOP_ITEMS: list[ShopItem] = [
    ShopItem(
        id="pzz_emel",
        title="ПЗЗ Емельяновский МО (GeoJSON)",
        description=(
            "Векторный слой зон ПЗЗ Емельяновского муниципального округа.\n"
            "54 000+ участков, 77 зон, заполненные атрибуты.\n"
            "Формат: GeoJSON (WGS 84)."
        ),
        price=3000,
        file_path="shop_files/pzz_emelyanovsky.geojson",
    ),
    ShopItem(
        id="pzz_divn",
        title="ПЗЗ Дивногорск (GeoJSON)",
        description=(
            "Векторный слой зон ПЗЗ городского округа Дивногорск.\n"
            "14 000+ участков, 32 зоны, заполненные атрибуты.\n"
            "Формат: GeoJSON (WGS 84)."
        ),
        price=3000,
        file_path="shop_files/pzz_divnogorsk.geojson",
    ),
    ShopItem(
        id="pzz_sosn",
        title="ПЗЗ Сосновоборск (GeoJSON)",
        description=(
            "Векторный слой зон ПЗЗ города Сосновоборска.\n"
            "Формат: GeoJSON (WGS 84)."
        ),
        price=3000,
        file_path="shop_files/pzz_sosnovoborsk.geojson",
    ),
    ShopItem(
        id="pzz_krsk_gpkg",
        title="ПЗЗ Красноярск (GeoPackage)",
        description=(
            "Векторный слой зон ПЗЗ Красноярского городского округа.\n"
            "Формат: GeoPackage (.gpkg) — готов для QGIS."
        ),
        price=5000,
        file_path="shop_files/pzz_krasnoyarsk.gpkg",
    ),
    ShopItem(
        id="qgis_full",
        title="QGIS-проект: ПЗЗ + кадастр + спутник",
        description=(
            "Готовый QGIS-проект: слои ПЗЗ, кадастровые участки, "
            "спутниковая подложка, настроенная стилизация.\n"
            "Формат: ZIP-архив с проектом и данными."
        ),
        price=10000,
        file_path="shop_files/qgis_project_full.zip",
    ),
]


def get_item(item_id: str) -> ShopItem | None:
    """Найти товар по id."""
    for item in SHOP_ITEMS:
        if item.id == item_id:
            return item
    return None
