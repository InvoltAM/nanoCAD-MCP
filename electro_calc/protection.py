"""Выбор и проверка аппаратов защиты и сечений кабелей.

Условия согласования (ПУЭ п. 3.1.11, ГОСТ Р 50571.4.41):
    Iр ≤ In автомата ≤ Iz кабеля
Проверка автоматического отключения питания:
    Iкз.min ≥ k · In, где k — верхняя кратность расцепителя (B=5, C=10, D=20),
    с коэффициентом запаса 1.2.
"""
from __future__ import annotations

from .cables import BREAKER_RATINGS, allowable_current, cable_params
from .models import Cable, Circuit, Phases

SC_SAFETY_FACTOR = 1.2
# Сопротивление внешней цепи (трансформатор + питающая сеть), типовое для
# городской квартиры, Ом — уточняется по данным сетевой организации
DEFAULT_EXTERNAL_LOOP_OHM = 0.4


def select_breaker(design_current_a: float) -> float:
    """Ближайший больший стандартный номинал автомата, А."""
    for rating in BREAKER_RATINGS:
        if rating >= design_current_a:
            return rating
    raise ValueError(
        f"Ток {design_current_a:.1f} А превышает максимальный номинал ряда "
        f"({BREAKER_RATINGS[-1]} А) — требуется разбиение на группы"
    )


def select_section(design_current_a: float, cable: Cable) -> float:
    """Минимальное сечение по условию Iz ≥ Iр, мм²."""
    from .cables import AVAILABLE_SECTIONS
    for section in AVAILABLE_SECTIONS:
        if allowable_current(section, cable.installation) >= design_current_a:
            return section
    raise ValueError(
        f"Ток {design_current_a:.1f} А выше допустимого для всех сечений справочника"
    )


def check_cable_protection(circuit: Circuit, design_current_a: float) -> dict:
    """Проверка цепочки Iр ≤ In ≤ Iz."""
    iz = allowable_current(circuit.cable.section_mm2, circuit.cable.installation)
    inom = circuit.device.rated_current_a
    checks = {
        "breaker_covers_load": inom >= design_current_a,
        "cable_protected": iz >= inom,
    }
    return {
        "circuit": circuit.name,
        "design_current_a": round(design_current_a, 2),
        "breaker_in_a": inom,
        "cable_iz_a": iz,
        "checks": checks,
        "passed": all(checks.values()),
    }


def min_short_circuit_current(cable: Cable, voltage_v: float,
                              external_loop_ohm: float = DEFAULT_EXTERNAL_LOOP_OHM
                              ) -> float:
    """Минимальный ток однофазного КЗ в конце линии, А.

    Iкз = Uф / (Rпетли), Rпетли = 2·L·r0 + Rвнеш.
    r0 берётся с поправкой на нагрев жилы (×1.25, +65 °C).
    """
    r0, _ = cable_params(cable.section_mm2)
    loop_ohm = 2.0 * (cable.length_m / 1000.0) * r0 * 1.25 + external_loop_ohm
    return voltage_v / loop_ohm


def check_sc_protection(circuit: Circuit, voltage_v: float,
                        external_loop_ohm: float = DEFAULT_EXTERNAL_LOOP_OHM
                        ) -> dict:
    """Проверка гарантированного отключения при КЗ (для 1ф линий)."""
    isc = min_short_circuit_current(circuit.cable, voltage_v, external_loop_ohm)
    required = circuit.device.curve.value * circuit.device.rated_current_a * SC_SAFETY_FACTOR
    return {
        "circuit": circuit.name,
        "isc_min_a": round(isc, 1),
        "required_a": round(required, 1),
        "passed": isc >= required,
    }
