"""Loader for non-secret presentation and parsing configuration.

Configuration lives in ``resources/ui_config.json`` so operators can adjust date
formats, sortable columns, analytics dimensions, and palettes without a code
change. Loaded once at import; the file ships inside the installed package.
"""
import json
from functools import lru_cache
from pathlib import Path
from typing import Any, Dict, List

_CONFIG_PATH = Path(__file__).parent / "resources" / "ui_config.json"


@lru_cache(maxsize=1)
def _load() -> Dict[str, Any]:
    with _CONFIG_PATH.open(encoding="utf-8") as handle:
        return json.load(handle)


# Parsing
DATE_INPUT_FORMATS: List[str] = _load()["date_input_formats"]
DATE_DISPLAY_FORMAT: str = _load()["date_display_format"]

# Pagination
_PAGINATION: Dict[str, int] = _load()["pagination"]
FALLBACK_LIMIT: int = _PAGINATION["fallback_limit"]
MAX_LIMIT: int = _PAGINATION["max_limit"]
PAGE_WINDOW: int = _PAGINATION["page_window"]

# Sorting
DEFAULT_SORT: str = _load()["default_sort"]
LOOKUP_BACKED_COLUMNS: Dict[str, str] = _load()["lookup_backed_columns"]
LIST_SORT_COLUMNS: List[Dict[str, str]] = _load()["list_sort_columns"]

# Analytics
ANALYTICS_DIMENSIONS: List[Dict[str, str]] = _load()["analytics_dimensions"]
ANALYTICS_PROJECTION_FIELDS: List[str] = _load()["analytics_projection_fields"]
SEVERITY_COLORS: Dict[str, str] = _load()["severity_colors"]
TREEMAP_PALETTE: List[str] = _load()["treemap_palette"]

# Lookup lists exposed to the filter UI, mapped to their lookup_values type.
LOOKUP_LISTS: Dict[str, str] = _load()["lookup_lists"]
