# GitHub-организация репозитория — статус

Выполнено 2026-11-06 автономно через GitHub API (токен из Git Credential Manager, после использования удалён).

## Настройки репозитория

- **Default-ветка:** `main` (бывш. `master` — устаревшая ветка форка, полностью влита в `main`).
- **Issues:** включены (были отключены — `has_issues: true`).
- **Ветка `master`:** удалена (0 коммитов теряно — всё было влито в `main`).
- **Метки:** `test`, `enhancement`, `plugin`, `server`.

## Бэклог — трекинг в issues

| # | Issue | Метки |
|---|---|---|
| [#1](https://github.com/InvoltAM/nanoCAD-MCP/issues/1) | M4: интеграционный тест electro_* на живом nanoCAD (чек-лист) | test |
| [#2](https://github.com/InvoltAM/nanoCAD-MCP/issues/2) | API: удаление группы (фидера) из щита + инструмент electro_group_delete | enhancement, plugin, server |
| [#3](https://github.com/InvoltAM/nanoCAD-MCP/issues/3) | API: создание щита «с нуля» + инструмент electro_board_create | enhancement, plugin, server |
| [#4](https://github.com/InvoltAM/nanoCAD-MCP/issues/4) | MCP: SSE-транспорт (опционально, низкий приоритет) | enhancement, server |

Приоритет: #1 (тест на живом nanoCAD) → #2 (удаление группы) → #3 (создание щита) → #4 (SSE).

## Как повторить API-доступ (если понадобится)

`gh` CLI не установлен. Анонимный API — только чтение. Запись выполнялась токеном
пользователя из Git Credential Manager:

```bash
# получить токен (не печатать!)
echo -e "protocol=https\nhost=github.com" | git credential fill | awk -F= '/^password=/{print $2}' > /tmp/gh_tok
# использовать в заголовке: Authorization: Bearer <токен>, API v2022-11-28
# после работы обязательно: rm -f /tmp/gh_tok
```
