"""Доменная модель электротехнического расчёта.

Сущности соответствуют объектной модели nanoCAD BIM Электро:
электроприёмник, групповая линия, щит, аппарат защиты, кабель.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum


class Phases(Enum):
    """Фазность линии/приёмника."""
    SINGLE = 1
    THREE = 3


class ReceiverKind(Enum):
    """Тип электроприёмника (определяет Кс по умолчанию)."""
    SOCKET = "розеточная сеть"
    LIGHTING = "освещение"
    COOKER = "электроплита"
    OVEN = "духовой шкаф"
    AC = "кондиционер"
    WM = "стиральная машина"
    DW = "посудомоечная машина"
    WH = "водонагреватель"
    FLOOR_HEATING = "тёплый пол"
    OTHER = "прочее"


class Installation(Enum):
    """Способ прокладки кабеля (влияет на допустимый ток)."""
    HIDDEN = "скрыто в штробе/под штукатуркой"
    OPEN = "открыто по стене"
    IN_DUCT = "в кабель-канале/коробе"


class BreakerCurve(Enum):
    """Характеристика расцепителя автомата."""
    B = 5   # кратность мгновенного расцепления (верхняя граница)
    C = 10
    D = 20


@dataclass
class Receiver:
    """Электроприёмник."""
    name: str
    power_kw: float
    cos_phi: float = 0.95
    demand_factor: float | None = None  # Кс; None — взять по умолчанию для типа
    kind: ReceiverKind = ReceiverKind.SOCKET
    phases: Phases = Phases.SINGLE
    room: str = ""


@dataclass
class Cable:
    """Кабельная линия."""
    brand: str = "ВВГнг(А)-LS"
    cores: int = 3
    section_mm2: float = 2.5
    length_m: float = 10.0
    installation: Installation = Installation.HIDDEN


@dataclass
class ProtectiveDevice:
    """Аппарат защиты групповой линии."""
    rated_current_a: float          # In автомата
    curve: BreakerCurve = BreakerCurve.C
    rcd_current_ma: float | None = 30  # IΔn УЗО/дифавтомата; None — без УЗО
    breaking_capacity_ka: float = 6.0


@dataclass
class Circuit:
    """Групповая линия: аппарат защиты + кабель + приёмники."""
    name: str
    cable: Cable
    device: ProtectiveDevice
    phases: Phases = Phases.SINGLE
    receivers: list[Receiver] = field(default_factory=list)


@dataclass
class Panel:
    """Групповой щит."""
    name: str
    supply_voltage_v: float = 220.0     # фазное для 1ф ввода
    supply_phases: Phases = Phases.SINGLE
    incoming_current_a: float = 40.0    # In вводного аппарата
    circuits: list[Circuit] = field(default_factory=list)
    demand_factor: float = 0.7          # Кс на вводе щита
