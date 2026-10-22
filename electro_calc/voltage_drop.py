"""Расчёт потерь напряжения в линиях (ГОСТ 32144-2013: суммарное ΔU ≤ 5 %).

Однофазная линия:  ΔU = 2 · I · L · (r0·cos φ + x0·sin φ)
Трёхфазная линия:  ΔU = √3 · I · L · (r0·cos φ + x0·sin φ)
r0, x0 приводятся из Ом/км, L — из метров.
"""
from __future__ import annotations

from .cables import cable_params
from .models import Cable, Circuit, Phases

MAX_TOTAL_DROP_PCT = 5.0  # ГОСТ 32144-2013


def _sin_phi(cos_phi: float) -> float:
    return (1.0 - cos_phi ** 2) ** 0.5


def voltage_drop_v(current_a: float, cable: Cable,
                   cos_phi: float, phases: Phases) -> float:
    """Потеря напряжения в линии, В."""
    r0, x0 = cable_params(cable.section_mm2)
    length_km = cable.length_m / 1000.0
    z = r0 * cos_phi + x0 * _sin_phi(cos_phi)
    factor = 2.0 if phases is Phases.SINGLE else 3 ** 0.5
    return factor * current_a * length_km * z


def voltage_drop_pct(current_a: float, cable: Cable,
                     cos_phi: float, phases: Phases,
                     voltage_v: float) -> float:
    """Потеря напряжения в линии, %."""
    return voltage_drop_v(current_a, cable, cos_phi, phases) / voltage_v * 100.0


def check_voltage_drop(circuit: Circuit, design_current_a: float,
                       cos_phi: float, voltage_v: float,
                       feed_drop_pct: float = 0.0) -> dict:
    """Проверка линии по потере напряжения.

    feed_drop_pct — потеря в питающей линии до щита (суммируется).
    """
    drop_pct = voltage_drop_pct(design_current_a, circuit.cable,
                                cos_phi, circuit.phases, voltage_v)
    total = drop_pct + feed_drop_pct
    return {
        "circuit": circuit.name,
        "drop_pct": round(drop_pct, 2),
        "total_drop_pct": round(total, 2),
        "limit_pct": MAX_TOTAL_DROP_PCT,
        "passed": total <= MAX_TOTAL_DROP_PCT,
    }
