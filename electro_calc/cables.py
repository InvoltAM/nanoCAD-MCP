"""Справочные данные кабелей с медными жилами (ПУЭ, табл. 1.3.4 и 1.3.6).

Iz — длительно допустимый ток, А.
r0 — активное сопротивление жилы при +20 °C, Ом/км (ГОСТ 22483-2012).
x0 — индуктивное сопротивление, Ом/км (типовое для силовых кабелей до 1 кВ).
"""
from __future__ import annotations

from .models import Installation

# section_mm2: (r0 Ом/км, x0 Ом/км, Iz скрыто А, Iz открыто А)
COPPER_CABLE_DB: dict[float, tuple[float, float, float, float]] = {
    1.5:  (12.10, 0.110, 19.0, 23.0),
    2.5:  (7.41,  0.104, 27.0, 30.0),
    4.0:  (4.61,  0.098, 36.0, 41.0),
    6.0:  (3.08,  0.093, 46.0, 50.0),
    10.0: (1.83,  0.086, 63.0, 80.0),
    16.0: (1.15,  0.081, 84.0, 100.0),
    25.0: (0.727, 0.078, 112.0, 140.0),
}

AVAILABLE_SECTIONS: tuple[float, ...] = tuple(sorted(COPPER_CABLE_DB))

# Стандартный ряд номиналов модульных автоматов, А (ГОСТ IEC 60898-1)
BREAKER_RATINGS: tuple[float, ...] = (6, 10, 13, 16, 20, 25, 32, 40, 50, 63)


class CableDataError(ValueError):
    """Сечение отсутствует в справочнике."""


def cable_params(section_mm2: float) -> tuple[float, float]:
    """Активное и индуктивное сопротивление жилы, Ом/км."""
    try:
        r0, x0, _, _ = COPPER_CABLE_DB[section_mm2]
    except KeyError as exc:
        raise CableDataError(
            f"Сечение {section_mm2} мм² отсутствует в справочнике "
            f"(доступны: {', '.join(map(str, AVAILABLE_SECTIONS))})"
        ) from exc
    return r0, x0


def allowable_current(section_mm2: float, installation: Installation) -> float:
    """Длительно допустимый ток Iz, А (с учётом способа прокладки)."""
    try:
        _, _, iz_hidden, iz_open = COPPER_CABLE_DB[section_mm2]
    except KeyError as exc:
        raise CableDataError(
            f"Сечение {section_mm2} мм² отсутствует в справочнике"
        ) from exc
    return iz_open if installation is Installation.OPEN else iz_hidden
