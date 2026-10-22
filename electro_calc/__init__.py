"""electro_calc — расчётный модуль электроснабжения (СП 256.1325800.2016, ПУЭ).

Независим от nanoCAD: чистый Python, тестируется автономно.
Результаты расчётов записываются в объекты модели BIM Электро через MCP-слой.
"""
from .cables import allowable_current, cable_params
from .loads import circuit_load, design_current, design_load, panel_load
from .models import (BreakerCurve, Cable, Circuit, Installation, Panel,
                     Phases, ProtectiveDevice, Receiver, ReceiverKind)
from .panel import validate_panel
from .protection import (check_cable_protection, check_sc_protection,
                         select_breaker, select_section)
from .voltage_drop import check_voltage_drop, voltage_drop_pct

__version__ = "0.1.0"

__all__ = [
    "BreakerCurve", "Cable", "Circuit", "Installation", "Panel", "Phases",
    "ProtectiveDevice", "Receiver", "ReceiverKind",
    "allowable_current", "cable_params",
    "circuit_load", "design_current", "design_load", "panel_load",
    "validate_panel",
    "check_cable_protection", "check_sc_protection",
    "select_breaker", "select_section",
    "check_voltage_drop", "voltage_drop_pct",
]
