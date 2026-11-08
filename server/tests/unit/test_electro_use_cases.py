"""Unit tests for ElectroUseCase (boards, group create/delete, equipment DB)."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from src.application.electro_use_cases import ElectroUseCase
from src.domain.exceptions import OperationError
from src.infrastructure.http_bridge import HttpCadBridge


@pytest.fixture
def mock_bridge() -> MagicMock:
    bridge = MagicMock(spec=HttpCadBridge)
    bridge.electro_get.return_value = {"success": True}
    return bridge


@pytest.fixture
def electro(mock_bridge: MagicMock) -> ElectroUseCase:
    return ElectroUseCase(mock_bridge)


class TestCreateGroup:
    def test_builds_path_and_returns_result(self, electro: ElectroUseCase, mock_bridge: MagicMock) -> None:
        mock_bridge.electro_get.return_value = {"success": True, "new_fider_ac_id": "1:2-0"}
        result = electro.create_group("10:20-0", "гр 7", automat_db_id=7, uzo_db_id=0)
        assert result["new_fider_ac_id"] == "1:2-0"
        path = mock_bridge.electro_get.call_args[0][0]
        assert path.startswith("/api/electro/model/group/create2?")
        assert "board=10%3A20-0" in path
        assert "name=%D0%B3%D1%80%207" in path  # «гр 7» (quote кодирует пробел как %20)
        assert "automat=7" in path
        assert "uzo=0" in path

    def test_requires_board_and_name(self, electro: ElectroUseCase) -> None:
        with pytest.raises(OperationError):
            electro.create_group("", "x")
        with pytest.raises(OperationError):
            electro.create_group("10:20-0", "")


class TestBoardGroups:
    def test_lists_groups_of_board(self, electro: ElectroUseCase, mock_bridge: MagicMock) -> None:
        mock_bridge.electro_get.return_value = {
            "success": True,
            "board": "Панель 1",
            "count": 2,
            "fiders": [
                {"ac_id": "1:2-0", "title": "гр 1-1", "role": "output", "automat": "ВА88-32"},
                {"ac_id": "1:3-0", "title": "Ввод 1", "role": "input", "automat": None},
            ],
        }
        result = electro.board_groups("10:20-0")
        assert result["count"] == 2
        assert result["fiders"][0]["automat"] == "ВА88-32"
        path = mock_bridge.electro_get.call_args[0][0]
        assert path == "/api/electro/model/board/fiders/10:20-0"

    def test_requires_board(self, electro: ElectroUseCase) -> None:
        with pytest.raises(OperationError):
            electro.board_groups("")


class TestDeleteGroup:
    def test_builds_path_and_returns_result(self, electro: ElectroUseCase, mock_bridge: MagicMock) -> None:
        mock_bridge.electro_get.return_value = {
            "success": True,
            "out_fiders_before": 8,
            "out_fiders_after": 7,
            "fider_gone_from_model": True,
        }
        result = electro.delete_group("10:20-0", "10:99-0")
        assert result["fider_gone_from_model"] is True
        path = mock_bridge.electro_get.call_args[0][0]
        assert path.startswith("/api/electro/model/group/delete?")
        assert "board=10%3A20-0" in path
        assert "fider=10%3A99-0" in path

    def test_requires_board_and_fider(self, electro: ElectroUseCase) -> None:
        with pytest.raises(OperationError):
            electro.delete_group("", "10:99-0")
        with pytest.raises(OperationError):
            electro.delete_group("10:20-0", "")


class TestBridgeErrors:
    def test_no_bridge_raises(self) -> None:
        electro = ElectroUseCase(None)
        with pytest.raises(OperationError):
            electro.delete_group("10:20-0", "10:99-0")

    def test_plugin_error_raises(self, electro: ElectroUseCase, mock_bridge: MagicMock) -> None:
        mock_bridge.electro_get.return_value = {"success": False, "error": "not found"}
        with pytest.raises(OperationError, match="not found"):
            electro.delete_group("10:20-0", "10:99-0")
