"""Use cases for nanoCAD BIM Электро (CAE model + equipment database).

Covers the electrical domain exposed by the CadEngine.Plugin HTTP API:
boards (щиты), fiders (группы), power calculation, and the equipment
catalog (автоматы / УЗО) used when creating new groups.

All methods talk to the plugin through HttpCadBridge.electro_get().
"""

from __future__ import annotations

import re
from typing import Any

from src.domain.exceptions import OperationError
from src.infrastructure.http_bridge import HttpCadBridge

_DEFAULT_LIMIT = 50
_MAX_LIMIT = 500


def _num(value: Any) -> float | None:
    """Parse a number from int/float/str with comma or dot decimal."""
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return float(value)
    try:
        return float(str(value).strip().replace(",", "."))
    except (TypeError, ValueError):
        return None


def _scale_values(scale: Any) -> list[float]:
    """Parse a current scale like '10/12.5/16/20' or '12,5' into floats."""
    if scale is None:
        return []
    out: list[float] = []
    for part in re.split(r"[/;]", str(scale)):
        part = part.strip()
        if not part:
            continue
        # '12,5' is a decimal comma, '10,12.5,16' with dots is ambiguous —
        # treat comma as decimal separator only when there is exactly one
        # comma and no dot in the part.
        v = _num(part)
        if v is not None:
            out.append(v)
    return out


def _matches_poles(record_poles: Any, want: str) -> bool:
    """Match poles: user passes '1P'/'3P'/'1P+N', records store 'PC_1P' etc."""
    if not want:
        return True
    w = want.upper().replace("PC_", "").replace(" ", "")
    have = str(record_poles or "").upper().replace("PC_", "").replace(" ", "")
    return w == have or w in have


def _clamp_limit(limit: int | None) -> int:
    if limit is None or limit <= 0:
        return _DEFAULT_LIMIT
    return min(limit, _MAX_LIMIT)


class ElectroUseCase:
    """Electrical domain: boards, power calc, equipment DB, group creation."""

    def __init__(self, bridge: HttpCadBridge | None) -> None:
        self._bridge = bridge

    # ── internal ──────────────────────────────────────────────

    def _get(self, path: str) -> dict[str, Any]:
        if self._bridge is None:
            raise OperationError(
                "HTTP bridge unavailable: .NET plugin is not connected. "
                "Start nanoCAD and load CadEngine.Plugin (NETLOAD)."
            )
        result = self._bridge.electro_get(path)
        if result is None:
            raise OperationError(f"No response from plugin for {path}")
        if result.get("success") is False:
            raise OperationError(str(result.get("error") or f"Plugin error on {path}"))
        return result

    # ── Модель: щиты и расчёт ─────────────────────────────────

    def list_boards(self) -> dict[str, Any]:
        """List all boards (щиты) in the current project."""
        data = self._get("/api/electro/model/boards")
        return {
            "count": data.get("count", 0),
            "boards": data.get("boards", []),
        }

    def board_groups(self, board_ac_id: str) -> dict[str, Any]:
        """List groups (фидеры) of a board without running a calculation."""
        if not board_ac_id:
            raise OperationError("board_ac_id is required (see electro_boards_list)")
        return self._get(f"/api/electro/model/board/fiders/{board_ac_id}")

    def board_calc(self, board_ac_id: str) -> dict[str, Any]:
        """Full power calculation of a board via the native Electra pipeline."""
        if not board_ac_id:
            raise OperationError("board_ac_id is required (see electro_boards_list)")
        return self._get(f"/api/electro/model/board/calc/{board_ac_id}")

    def dump_node(self, ac_id: str) -> dict[str, Any]:
        """Dump all properties of a CAE model node (diagnostics)."""
        if not ac_id:
            raise OperationError("ac_id is required")
        return self._get(f"/api/electro/model/node/{ac_id}")

    # ── БД оборудования ───────────────────────────────────────

    def list_db_automats(
        self,
        query: str | None = None,
        poles: str | None = None,
        characteristic: str | None = None,
        current: float | None = None,
        limit: int | None = None,
    ) -> dict[str, Any]:
        """Search circuit breakers in the equipment DB with filters.

        - query: substring of name/series (case-insensitive)
        - poles: '1P', '2P', '3P', '4P', '1P+N' (matches PC_* codes)
        - characteristic: 'B', 'C', 'D', 'K', 'Z' (trip curve letter)
        - current: trip rating in amps; matches against current_scale
          (the real adjustable/trip ratings), falling back to nominal_cur
        """
        data = self._get("/api/electro/db/automats")
        items: list[dict[str, Any]] = data.get("automats", [])

        ch = (characteristic or "").strip().upper()[:1] or None
        q = (query or "").strip().lower()

        out: list[dict[str, Any]] = []
        for it in items:
            if q and q not in str(it.get("name", "")).lower() \
                    and q not in str(it.get("series", "")).lower():
                continue
            if poles and not _matches_poles(it.get("poles"), poles):
                continue
            if ch and not str(it.get("characteristic", "")).upper().startswith(ch):
                continue
            if current is not None:
                scale = _scale_values(it.get("current_scale"))
                if scale:
                    if not any(abs(v - current) < 0.01 for v in scale):
                        continue
                else:
                    nom = _num(it.get("nominal_cur"))
                    if nom is None or abs(nom - current) > 0.01:
                        continue
            out.append(it)

        total = len(out)
        return {
            "count_total": total,
            "count": min(total, _clamp_limit(limit)),
            "automats": out[: _clamp_limit(limit)],
        }

    def list_db_uzo(
        self,
        query: str | None = None,
        poles: str | None = None,
        current: float | None = None,
        leakage_ma: float | None = None,
        limit: int | None = None,
    ) -> dict[str, Any]:
        """Search RCDs (УЗО) in the equipment DB with filters.

        - query: substring of name (case-insensitive)
        - poles: '2P', '4P' (matches PC_* codes)
        - current: nominal current in amps (nominal_cur)
        - leakage_ma: leakage trip current, e.g. 30 / 100 / 300
        """
        data = self._get("/api/electro/db/uzo")
        items: list[dict[str, Any]] = data.get("uzo", [])

        q = (query or "").strip().lower()

        out: list[dict[str, Any]] = []
        for it in items:
            if q and q not in str(it.get("name", "")).lower():
                continue
            if poles and not _matches_poles(it.get("poles"), poles):
                continue
            if current is not None:
                nom = _num(it.get("nominal_cur"))
                if nom is None or abs(nom - current) > 0.01:
                    continue
            if leakage_ma is not None:
                scale = _scale_values(it.get("uzo_current_scale"))
                if scale and not any(abs(v - leakage_ma) < 0.01 for v in scale):
                    continue
            out.append(it)

        total = len(out)
        return {
            "count_total": total,
            "count": min(total, _clamp_limit(limit)),
            "uzo": out[: _clamp_limit(limit)],
        }

    # ── Создание группы ───────────────────────────────────────

    def create_group(
        self,
        board_ac_id: str,
        name: str,
        automat_db_id: int = 0,
        uzo_db_id: int = 0,
    ) -> dict[str, Any]:
        """Create a new outgoing group (фидер) on a board.

        automat_db_id / uzo_db_id come from electro_db_automats /
        electro_db_uzo (field db_id). Pass 0 to skip the apparatus.
        """
        if not board_ac_id:
            raise OperationError("board_ac_id is required (see electro_boards_list)")
        if not name:
            raise OperationError("name is required, e.g. 'гр 7'")
        from urllib.parse import quote

        path = (
            "/api/electro/model/group/create2"
            f"?board={quote(board_ac_id, safe='')}"
            f"&name={quote(name, safe='')}"
            f"&automat={int(automat_db_id)}"
            f"&uzo={int(uzo_db_id)}"
        )
        return self._get(path)

    def delete_group(self, board_ac_id: str, fider_ac_id: str) -> dict[str, Any]:
        """Delete an outgoing group (фидер) from a board by its ac_id.

        fider_ac_id is the ac_id of the group (see electro_board_calc field
        ac_id). Input fiders cannot be deleted.
        """
        if not board_ac_id:
            raise OperationError("board_ac_id is required (see electro_boards_list)")
        if not fider_ac_id:
            raise OperationError("fider_ac_id is required (see electro_board_calc)")
        from urllib.parse import quote

        path = (
            "/api/electro/model/group/delete"
            f"?board={quote(board_ac_id, safe='')}"
            f"&fider={quote(fider_ac_id, safe='')}"
        )
        return self._get(path)
