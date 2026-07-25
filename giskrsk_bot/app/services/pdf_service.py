"""Сервис генерации PDF-отчётов (ленивый импорт WeasyPrint)."""

from __future__ import annotations

import logging
import os
from datetime import datetime

from app.core.config import settings

logger = logging.getLogger(__name__)

PDF_TEMPLATE = """<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<style>
body {{ font-family: 'DejaVu Sans', sans-serif; font-size: 12px; color: #333; }}
h1 {{ color: #2c3e50; font-size: 18px; }}
.header {{ text-align: center; margin-bottom: 20px; }}
.section {{ margin: 15px 0; }}
table {{ width: 100%; border-collapse: collapse; }}
td, th {{ border: 1px solid #ddd; padding: 8px; text-align: left; }}
th {{ background-color: #f5f5f5; }}
.label {{ font-weight: bold; width: 200px; }}
.footer {{ margin-top: 30px; font-size: 10px; color: #999; }}
</style>
</head>
<body>
<div class="header">
<h1>📋 Отчёт по земельному участку</h1>
<p>ГИС Красноярье — дата: {{ date }}</p>
</div>
<div class="section">
<h2>📍 Участок: {{ cadastral_number }}</h2>
<table>
<tr><td class="label">Кадастровый номер</td><td>{{ cadastral_number }}</td></tr>
<tr><td class="label">Зона ПЗЗ</td><td>{{ zone_code }}</td></tr>
<tr><td class="label">Название зоны</td><td>{{ zone_name }}</td></tr>
<tr><td class="label">ВРИ</td><td>{{ vri }}</td></tr>
<tr><td class="label">Площадь</td><td>{{ area_m2 }}</td></tr>
<tr><td class="label">Кадастровая стоимость</td><td>{{ cadastral_value }}</td></tr>
</table>
</div>
<div class="footer">
<p>Сформировано автоматически ботом «ГИС Красноярье»</p>
<p>{{ date }}</p>
</div>
</body>
</html>"""


class PdfService:
    """Генерация PDF-отчётов по участкам.
    
    WeasyPrint подгружается лениво, только при вызове generate_report.
    Если GTK-библиотеки не установлены — возвращает None без падения.
    """

    def __init__(self) -> None:
        os.makedirs(settings.PDF_OUTPUT_DIR, exist_ok=True)
        self._weasyprint_available: bool | None = None

    def _check_available(self) -> bool:
        """Проверить доступность WeasyPrint."""
        if self._weasyprint_available is not None:
            return self._weasyprint_available
        try:
            import weasyprint  # noqa: F401
            self._weasyprint_available = True
        except Exception:
            logger.warning("WeasyPrint not available (GTK libraries missing)")
            self._weasyprint_available = False
        return self._weasyprint_available

    def generate_report(self, parcel_data: dict) -> str | None:
        """Сгенерировать PDF-файл. Возвращает путь к файлу или None."""
        if not self._check_available():
            return None

        from weasyprint import HTML

        cadnum = parcel_data.get("cadastral_number", "unknown")
        filename = f"parcel_{cadnum.replace(':', '_')}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf"
        filepath = os.path.join(settings.PDF_OUTPUT_DIR, filename)

        html_content = PDF_TEMPLATE.format(
            date=datetime.now().strftime("%d.%m.%Y %H:%M"),
            cadastral_number=parcel_data.get("cadastral_number", ""),
            zone_code=parcel_data.get("zone_code", "—"),
            zone_name=parcel_data.get("zone_name", "—"),
            vri=parcel_data.get("vri", "—"),
            area_m2=parcel_data.get("area_m2", "—"),
            cadastral_value=parcel_data.get("cadastral_value", "—"),
        )

        try:
            HTML(string=html_content).write_pdf(filepath)
            logger.info("PDF generated: %s", filepath)
            return filepath
        except Exception as e:
            logger.error("PDF generation error: %s", e)
            return None
