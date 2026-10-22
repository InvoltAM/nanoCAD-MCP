"""Комплексный расчёт и валидация щита: точка входа модуля."""
from __future__ import annotations

from .loads import _weighted_cos_phi, circuit_load, design_load, panel_load
from .models import Panel
from .protection import check_cable_protection, check_sc_protection
from .voltage_drop import check_voltage_drop


def validate_panel(panel: Panel, feed_drop_pct: float = 0.0) -> dict:
    """Полная проверка щита: нагрузки, защита, ΔU, КЗ.

    Возвращает структуру, пригодную для отдачи AI-агенту через MCP.
    """
    summary = panel_load(panel)
    issues: list[str] = []
    circuits_report = []

    for circuit, load in zip(panel.circuits, summary["groups"]):
        cos_phi = _weighted_cos_phi(circuit.receivers)
        protection = check_cable_protection(circuit, load["design_current_a"])
        drop = check_voltage_drop(circuit, load["design_current_a"],
                                  cos_phi, panel.supply_voltage_v,
                                  feed_drop_pct)
        sc = check_sc_protection(circuit, panel.supply_voltage_v)

        for report in (protection, drop, sc):
            if not report["passed"]:
                issues.append(f"{circuit.name}: {_describe_failure(report)}")

        circuits_report.append({
            **load, "protection": protection, "voltage_drop": drop,
            "short_circuit": sc,
        })

    if summary["design_current_a"] > panel.incoming_current_a:
        issues.append(
            f"Вводной аппарат {panel.incoming_current_a} А меньше расчётного "
            f"тока ввода {summary['design_current_a']} А"
        )

    return {
        "panel": summary,
        "circuits": circuits_report,
        "issues": issues,
        "passed": not issues,
    }


def _describe_failure(report: dict) -> str:
    if "cable_iz_a" in report:  # protection
        if not report["checks"]["breaker_covers_load"]:
            return (f"автомат {report['breaker_in_a']} А не покрывает "
                    f"расчётный ток {report['design_current_a']} А")
        return (f"кабель не защищён: Iz={report['cable_iz_a']} А < "
                f"In={report['breaker_in_a']} А — увеличьте сечение")
    if "drop_pct" in report:  # voltage drop
        return (f"потеря напряжения {report['total_drop_pct']}% превышает "
                f"{report['limit_pct']}% — увеличьте сечение или сократите трассу")
    return (f"ток КЗ {report['isc_min_a']} А недостаточен для расцепления "
            f"(требуется {report['required_a']} А) — увеличьте сечение "
            f"или смените характеристику автомата")
