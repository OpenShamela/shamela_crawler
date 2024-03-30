import json
from io import BytesIO
from typing import Any

from scrapy.exporters import JsonItemExporter


class SortedJsonItemExporter(JsonItemExporter):
    def __init__(self, file: BytesIO, **kwargs: Any) -> None:
        super().__init__(file, **kwargs)
        self._items: list[dict[str, Any]] = []

    def export_item(self, item: dict[str, Any]) -> None:
        self._items.append(dict(self._get_serialized_fields(item)))

    def start_exporting(self) -> None:
        pass

    def finish_exporting(self) -> None:
        self._items.sort(key=lambda x: x.get('id', 0))
        self.file.write(json.dumps(self._items, ensure_ascii=False, indent=1).encode('utf-8'))
