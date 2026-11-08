# AGENTS.md — nanoCAD-MCP (fork InvoltAM)

## Что это

MCP-сервер для управления nanoCAD 26 / BIM Электро 26 из ИИ-агента.
Форк Evans-Sense/nanoCAD-MCP. Репозиторий: https://github.com/InvoltAM/nanoCAD-MCP

## Архитектура

- `engine/CadEngine.Plugin/` — плагин .NET 6 (net6.0-windows) для nanoCAD.
  Загружается через NETLOAD, поднимает HTTP-сервер `HttpListener` на `http://localhost:5080/`
  (порт переопределяется env `NANOCAD_MCP_PORT`, пишется в `%LOCALAPPDATA%\Temp\ncad-mcp-port.txt`).
  Маршруты: `/api/system/health`, 3D-фичи, и блок `/api/electro/*` (маршруты в `HttpServer.cs`).
- `server/` — Python MCP-сервер (mcp 1.27.1), stdio-транспорт.
  Команда запуска: `ncad-mcp` (ставится `pip install -e .`).
  Определения инструментов: `server/src/presentation/tool_defs.py`.
  Мост к плагину: `server/src/infrastructure/http_bridge.py` (читает порт из temp-файла).
- `electro_calc/` — нативный расчёт электроснабжения (вынос нативного пайплайна Электро).
- `tests/` — unit-тесты сервера.
- `docs/` — исследования: реверс-анализ объектов Электро (1–3), схемы архитектуры.
- `scripts/` — PowerShell-пробы разведки БД/объектов Электро.

## Статус (2026-11-06)

Выполнено и запушено (ветка main):
- M0 — разведка окружения, M1 — дамп объектов Электро, M2 — чтение/запись CAE-модели,
  M3 — создание групп из БД + нативный расчёт мощности (проверено: 155,36 kW совпало с Электро),
  M4 — 6 инструментов `electro_*` (213 инструментов всего), unit-тесты зелёные.

M4-интеграционный тест на живом nanoCAD 26 — ПРОЙДЕН (2026-11-06, все 8 шагов,
эталон 155,36 kW подтверждён; отчёт — в issue #1). Трекинг задач — в GitHub issues.

## Правила разработки (обязательны)

1. Весь код пишет ассистент; пользователь только выполняет команды
   (dotnet build, git apply, NETLOAD) и присылает вывод.
2. Папку `patches/` НИКОГДА не коммитить в репозиторий (локальные патчи-заготовки).
3. Крупные изменения плагина поставлять пользователю как git-патчи
   (`git diff <sha> HEAD -- engine/` или `-- server/`), применяемые через `git apply`.
4. После правок C# — `dotnet build` должен быть зелёным до передачи пользователю.
5. Документацию по исследованиям складывать в `docs/`, пробы — в `scripts/`.

## Как запускать

1. nanoCAD → `NETLOAD` → `CadEngine.Plugin.dll` → проверить `http://localhost:5080/api/system/health`.
2. MCP-клиент (Kimi Code / VS Code) поднимает сервер сам через конфиг `.kimi-code/mcp.json`
   (`ncad-mcp`). В консоль stdio-сервера команды не вводить — только JSON-RPC от клиента.
   Все узлы (nanoCAD, плагин, MCP-сервер, клиент) должны быть на одной машине.

## Чек-лист интеграционного теста M4

Пройден 2026-11-06 (nanoCAD 26.0.7410.4946). Подробный отчёт с результатами —
в issue #1. Прямая проверка без MCP-клиента (PowerShell):
```powershell
Invoke-RestMethod http://localhost:5080/api/system/health
Invoke-RestMethod http://localhost:5080/api/electro/model/boards
Invoke-RestMethod "http://localhost:5080/api/electro/model/board/calc/<AC_ID>"
Invoke-RestMethod "http://localhost:5080/api/electro/db/automats?query=ВА47&poles=1P&characteristic=C&current=16"
```

## Бэклог (трекинг — в GitHub issues)

- #3 API: создание щита «с нуля» + `electro_board_create`.
- #4 MCP: SSE-транспорт (опционально, низкий приоритет).

Закрыто: #5 — неинтерактивная привязка аппаратов в `electro_group_create`
(виновник модального диалога — `SelectDbObject`, заменён; исправление подтверждено
на живом nanoCAD: ~1 с, без диалогов, сверка DbId в `steps`).
Закрыто: #2 — `electro_group_delete` (endpoint + MCP-инструмент, 214 всего;
удаление через `IAcadObject.Delete()`, подтверждено на живом nanoCAD: ~0,4 с,
тестовые группы с обеих панелей удалены, расчёт не изменился).
