"""Расчёт электрических нагрузок (СП 256.1325800.2016).

Метод коэффициента спроса: Pр = Кс · ΣPуст.
Коэффициенты спроса по умолчанию — по табл. 7.6 СП 256.1325800.2016
и типовой проектной практике для жилых зданий.
"""
from __future__ import annotations

from .models import Circuit, Panel, Phases, Receiver, ReceiverKind

# Коэффициенты спроса по умолчанию для типов приёмников квартиры
DEFAULT_DEMAND_FACTORS: dict[ReceiverKind, float] = {
    ReceiverKind.SOCKET: 0.7,
    ReceiverKind.LIGHTING: 0.85,
    ReceiverKind.COOKER: 0.9,
    ReceiverKind.OVEN: 0.9,
    ReceiverKind.AC: 0.8,
    ReceiverKind.WM: 0.9,
    ReceiverKind.DW: 0.9,
    ReceiverKind.WH: 0.9,
    ReceiverKind.FLOOR_HEATING: 0.8,
    ReceiverKind.OTHER: 0.8,
}


def demand_factor_of(receiver: Receiver) -> float:
    """Кс приёмника: явно заданный или по умолчанию для его типа."""
    if receiver.demand_factor is not None:
        return receiver.demand_factor
    return DEFAULT_DEMAND_FACTORS[receiver.kind]


def installed_load(receivers: list[Receiver]) -> float:
    """Установленная мощность группы, кВт."""
    return sum(r.power_kw for r in receivers)


def design_load(receivers: list[Receiver]) -> float:
    """Расчётная мощность группы, кВт: Σ(Pуст · Кс)."""
    return sum(r.power_kw * demand_factor_of(r) for r in receivers)


def design_current(power_kw: float, voltage_v: float,
                   cos_phi: float, phases: Phases) -> float:
    """Расчётный ток линии, А.

    Однофазная: I = P / (Uф · cos φ)
    Трёхфазная: I = P / (√3 · Uл · cos φ), Uл = линейное напряжение
    """
    power_w = power_kw * 1000.0
    if phases is Phases.SINGLE:
        return power_w / (voltage_v * cos_phi)
    return power_w / (3 ** 0.5 * voltage_v * cos_phi)


def circuit_load(circuit: Circuit, voltage_v: float) -> dict:
    """Сводка нагрузки групповой линии."""
    p_inst = installed_load(circuit.receivers)
    p_des = design_load(circuit.receivers)
    cos_phi = _weighted_cos_phi(circuit.receivers)
    current = design_current(p_des, voltage_v, cos_phi, circuit.phases)
    return {
        "circuit": circuit.name,
        "installed_kw": round(p_inst, 3),
        "design_kw": round(p_des, 3),
        "cos_phi": round(cos_phi, 3),
        "design_current_a": round(current, 2),
    }


def panel_load(panel: Panel) -> dict:
    """Сводка нагрузки щита: сумма расчётных нагрузок групп с Кс на вводе."""
    groups = [circuit_load(c, panel.supply_voltage_v) for c in panel.circuits]
    p_inst = installed_load([r for c in panel.circuits for r in c.receivers])
    p_des_groups = sum(g["design_kw"] for g in groups)
    p_des_panel = p_des_groups * panel.demand_factor
    cos_phi = _weighted_cos_phi([r for c in panel.circuits for r in c.receivers])
    current = design_current(p_des_panel, panel.supply_voltage_v,
                             cos_phi, panel.supply_phases)
    return {
        "panel": panel.name,
        "installed_kw": round(p_inst, 3),
        "design_kw": round(p_des_panel, 3),
        "cos_phi": round(cos_phi, 3),
        "design_current_a": round(current, 2),
        "incoming_current_a": panel.incoming_current_a,
        "groups": groups,
    }


def _weighted_cos_phi(receivers: list[Receiver]) -> float:
    """Средневзвешенный cos φ по установленной мощности."""
    total = sum(r.power_kw for r in receivers)
    if total == 0:
        return 0.95
    return sum(r.power_kw * r.cos_phi for r in receivers) / total
