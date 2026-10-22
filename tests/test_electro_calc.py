"""Тесты electro_calc: эталонные примеры, посчитанные вручную."""
import pytest

from electro_calc import (BreakerCurve, Cable, Circuit, Installation, Panel,
                          Phases, ProtectiveDevice, Receiver, ReceiverKind,
                          allowable_current, check_voltage_drop,
                          design_current, select_breaker, select_section,
                          validate_panel, voltage_drop_pct)


# --- Нагрузки и токи -------------------------------------------------------

def test_design_current_single_phase():
    # 3 кВт, 220 В, cos φ = 0.95 → I = 3000 / (220·0.95) ≈ 14.35 А
    assert design_current(3.0, 220, 0.95, Phases.SINGLE) == pytest.approx(14.35, abs=0.01)


def test_design_current_three_phase():
    # 10 кВт, 380 В, cos φ = 0.95 → I = 10000 / (√3·380·0.95) ≈ 15.99 А
    assert design_current(10.0, 380, 0.95, Phases.THREE) == pytest.approx(15.99, abs=0.01)


def test_select_breaker():
    assert select_breaker(14.35) == 16
    assert select_breaker(16.0) == 16
    assert select_breaker(16.1) == 20
    with pytest.raises(ValueError):
        select_breaker(70.0)


def test_select_section():
    # 14.35 А скрытая прокладка → 1.5 мм² (Iz=19)
    assert select_section(14.35, Cable(installation=Installation.HIDDEN)) == 1.5
    # 25 А → 2.5 мм² (Iz=27)
    assert select_section(25.0, Cable(installation=Installation.HIDDEN)) == 2.5


# --- Потери напряжения -----------------------------------------------------

def test_voltage_drop_single_phase():
    # ВВГнг 3×2.5, 20 м, 14.35 А, cos φ=0.95
    # ΔU = 2 · 14.35 · 0.02 · (7.41·0.95 + 0.104·0.312) ≈ 4.06 В → 1.85 %
    cable = Cable(section_mm2=2.5, length_m=20)
    drop = voltage_drop_pct(14.35, cable, 0.95, Phases.SINGLE, 220)
    assert drop == pytest.approx(1.85, abs=0.05)


def test_voltage_drop_limit_check():
    cable = Cable(section_mm2=1.5, length_m=60)
    circuit = Circuit(name="гр.1", cable=cable,
                      device=ProtectiveDevice(rated_current_a=16))
    # 16 А на 60 м по 1.5 мм²: ΔU ≈ 5.4 % → не проходит
    result = check_voltage_drop(circuit, 16.0, 0.95, 220)
    assert not result["passed"]
    assert result["total_drop_pct"] > 5.0


# --- Защита и КЗ -----------------------------------------------------------

def test_allowable_current():
    assert allowable_current(2.5, Installation.HIDDEN) == 27.0
    assert allowable_current(2.5, Installation.OPEN) == 30.0


# --- Комплексная валидация: эталонная квартира ------------------------------

def make_apartment_panel() -> Panel:
    sockets_kitchen = Circuit(
        name="гр.1 Розетки кухни",
        cable=Cable(section_mm2=2.5, length_m=18),
        device=ProtectiveDevice(rated_current_a=20, curve=BreakerCurve.C),
        receivers=[
            Receiver("Розетки столешницы", 2.5, kind=ReceiverKind.SOCKET),
            Receiver("Посудомоечная машина", 2.0, kind=ReceiverKind.DW),
            Receiver("Холодильник", 0.3, kind=ReceiverKind.OTHER),
        ],
    )
    lighting = Circuit(
        name="гр.2 Освещение",
        cable=Cable(section_mm2=1.5, length_m=25),
        device=ProtectiveDevice(rated_current_a=10, curve=BreakerCurve.B),
        receivers=[
            Receiver("Освещение комнат", 0.8, kind=ReceiverKind.LIGHTING),
            Receiver("Освещение кухни", 0.3, kind=ReceiverKind.LIGHTING),
        ],
    )
    cooker = Circuit(
        name="гр.3 Электроплита",
        cable=Cable(section_mm2=4.0, length_m=12),
        device=ProtectiveDevice(rated_current_a=32, curve=BreakerCurve.C,
                                rcd_current_ma=None),
        receivers=[Receiver("Варочная панель", 7.0, kind=ReceiverKind.COOKER)],
    )
    return Panel(name="ЩК", supply_voltage_v=220, incoming_current_a=40,
                 circuits=[sockets_kitchen, lighting, cooker])


def test_valid_apartment_panel_passes():
    result = validate_panel(make_apartment_panel())
    assert result["passed"], f"Замечания: {result['issues']}"
    assert result["panel"]["design_current_a"] <= 40


def test_undersized_cable_detected():
    panel = make_apartment_panel()
    # Автомат 25 А при Iz кабеля 1.5 мм² = 19 А → кабель не защищён
    panel.circuits[0].cable.section_mm2 = 1.5
    panel.circuits[0].device.rated_current_a = 25
    result = validate_panel(panel)
    assert not result["passed"]
    assert any("не защищён" in i for i in result["issues"])


def test_panel_load_summary():
    summary = validate_panel(make_apartment_panel())["panel"]
    # ΣPуст = 2.5+2.0+0.3+0.8+0.3+7.0 = 12.9 кВт
    assert summary["installed_kw"] == pytest.approx(12.9, abs=0.01)
    # Расчётная нагрузка меньше установленной
    assert summary["design_kw"] < summary["installed_kw"]
