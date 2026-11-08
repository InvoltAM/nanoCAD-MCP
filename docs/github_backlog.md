# GitHub-бэклог: issues и настройка репозитория

Подготовлено 2026-11-06. Репозиторий: https://github.com/InvoltAM/nanoCAD-MCP

Состояние на момент подготовки:

- Вся работа (M0–M4) в ветке `main`; `master` — устаревшая ветка форка, на 35 коммитов позади, полностью влита в `main`.
- Issues и PR на GitHub отсутствуют; бэклог жил только в `AGENTS.md`.

---

## Шаг 1. Сменить default-ветку на `main`

Выполняется в браузере, ~2 минуты:

1. Открыть https://github.com/InvoltAM/nanoCAD-MCP/settings/branches
2. Нажать «⋮» (справа от `master`, сейчас default) → **Switch default branch** → выбрать `main` → **Update**.
3. Опционально: после смены default ветку `master` можно удалить
   (https://github.com/InvoltAM/nanoCAD-MCP/branches → иконка корзины у `master`).
   Безопасно: `git rev-list --count origin/main..origin/master` = 0, всё из `master` уже в `main`.

> Быстрый вариант из консоли (если установлен `gh` с правами на репозиторий):
> `gh api -X PATCH repos/InvoltAM/nanoCAD-MCP -f default_branch=main`

---

## Шаг 2. Завести issues

Ниже — 4 готовых текста. Копируйте заголовок и тело как есть
(https://github.com/InvoltAM/nanoCAD-MCP/issues/new). Порядок = приоритет.

---

### Issue 1

**Заголовок:** `M4: интеграционный тест electro_* на живом nanoCAD (чек-лист)`

**Тело:**

```markdown
M4 реализован и запушен (6 инструментов `electro_*`, 213 инструментов всего, unit-тесты зелёные). Осталось подтвердить на живом nanoCAD 26.

**Предусловие:** nanoCAD запущен, плагин загружен через NETLOAD, `http://localhost:5080/api/system/health` отвечает.

Порядок важен — каждый шаг опирается на предыдущий:

- [ ] 1. `electro_boards_list` — список щитов, взять `ac_id`.
- [ ] 2. `electro_node_dump` (ac_id) — дамп узла, подтверждение чтения модели.
- [ ] 3. `electro_board_calc` (board_ac_id) — нативный расчёт; сверить итоги с Электро (эталон на тестовом щите: **155,36 kW**).
- [ ] 4. `electro_db_automats` (query/poles/characteristic/current) — каталог автоматов, взять `db_id`.
- [ ] 5. `electro_db_uzo` (poles/current/leakage_ma) — каталог УЗО (можно пропустить: uzo_db_id=0).
- [ ] 6. `electro_group_create` (board_ac_id, name, automat_db_id, uzo_db_id) — создать фидер, модель сохраняется.
- [ ] 7. Проверить в nanoCAD: группа появилась на щите, обновить дерево проекта.
- [ ] 8. `electro_board_calc` повторно — щит считается уже с новой группой.

Прямая проверка без MCP-клиента (PowerShell):

```powershell
Invoke-RestMethod http://localhost:5080/api/system/health
Invoke-RestMethod http://localhost:5080/api/electro/model/boards
Invoke-RestMethod "http://localhost:5080/api/electro/model/board/calc/<AC_ID>"
Invoke-RestMethod "http://localhost:5080/api/electro/db/automats?query=ВА47&poles=1P&characteristic=C&current=16"
```

Результат теста зафиксировать комментарием к этому issue.
```

---

### Issue 2

**Заголовок:** `API: удаление группы (фидера) из щита + инструмент electro_group_delete`

**Тело:**

```markdown
Сейчас через API можно только создавать группы (`/api/electro/model/group/create2`, инструмент `electro_group_create`). Нужна обратная операция — удаление отходящего фидера из щита.

**Зачем:**
- Чистка тестовых групп (MCP-TEST / TEST-M3) со старого чертежа.
- Полный цикл редактирования схемы через MCP.

**Что сделать:**
- Endpoint в плагине: `GET /api/electro/model/group/delete/{boardAcId}/{fiderAcId}` (или POST) — найти фидер по AcId в `OutFiders` щита, удалить штатным способом, `SaveObject(board, true, paperId)`.
- MCP-инструмент `electro_group_delete` (определение в `server/src/presentation/tool_defs.py`, маршрут в `use_case_factory.py`/`_TOOL_HANDLER_MAP`, метод в `ElectroUseCase`).
- Unit-тесты серверной части.

**Открытый вопрос:** штатный путь удаления не разведан. Кандидаты: удаление из коллекции `OutFiders` + `SaveObject`, либо штатный сервис из DI-контейнера (искать аналог `IDbElFiderCraetor` — например, сервис удаления/редактирования фидеров). Разведка — первый шаг, реализация через рефлексию по установленному паттерну (`ElectroModelService.CreateGroup`).

**Контекст:** см. `docs/Реверс-анализ_Электро_3.md` (карта доступа к CAE-модели, проверенный сценарий создания группы).
```

---

### Issue 3

**Заголовок:** `API: создание щита «с нуля» + инструмент electro_board_create`

**Тело:**

```markdown
Сейчас API работает с существующими щитами (чтение, расчёт, создание групп внутри). Следующий шаг — создавать сам щит программно.

**Что сделать:**
- Разведка: как Электро создаёт `ElBoard` (какой сервис/фабрика из DI-контейнера, какие обязательные поля: Db-запись DbElBoard, слой `ЭЛ_ШКАФЫ`, позиция на чертеже, маски имён групп).
- Endpoint в плагине: `/api/electro/model/board/create` (параметры: имя/марка, напряжение, тип монтажа).
- MCP-инструмент `electro_board_create`.
- Unit-тесты серверной части.

**Паттерн реализации:** полностью через рефлексию, без compile-time ссылок на сборки Электро (как весь `ElectroModelService`). Создание группы — ближайший образец (`CreateGroup`, `docs/Реверс-анализ_Электро_3.md`).

**Сложность выше средней:** разведки по созданию ElBoard не проводилось, возможны итерации на живом nanoCAD. Зависит от результатов issue M4-интеграционного теста.
```

---

### Issue 4

**Заголовок:** `MCP: SSE-транспорт (опционально, низкий приоритет)`

**Тело:**

```markdown
Сейчас MCP-сервер работает только по stdio (команда `ncad-mcp`), что требует запуска клиента на той же машине, что и nanoCAD.

**Идея:** добавить SSE-транспорт (`mcp` 1.27.1 поддерживает) — тогда MCP-клиент сможет подключаться к серверу удалённо, nanoCAD остаётся только на рабочей станции с плагином.

**Ограничения, которые никуда не денутся:** плагин (`HttpListener` на localhost:5080) и MCP-сервер всё равно должны быть на машине с nanoCAD; меняется только способ подключения клиента.

Приоритет низкий: текущий сценарий «всё на одной машине» покрывается stdio.
```

---

## После выполнения

- Закрыть это планирование: удалить упоминание «бэклог живёт в AGENTS.md» из разговоров, трекинг дальше ведём в issues.
- Метки (labels), если заведёте: `test`, `enhancement`, `plugin`, `server`.
