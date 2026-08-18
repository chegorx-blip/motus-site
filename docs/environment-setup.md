# Environment setup — снимок конфигурации (для переноса на другую машину)

**Снято:** 2026-08-18
**Зачем:** чтобы новая сессия Claude Code на другой машине могла понять, что было настроено здесь, и знала, что нужно воспроизвести.

---

## 1. MCP-серверы

### Локальные (нужно установить/запустить заново на новой машине)

| Имя | Тип | Область конфига | Команда/URL | Что даёт |
|---|---|---|---|---|
| `workspace-mcp` | http | `~/.mcp.json` (user-level) | `http://localhost:8000/mcp` | Gmail, Calendar, Drive, Sheets, Docs, Slides, Forms, Apps Script, Tasks, Contacts — локальный сервер, надо поднять отдельно (репозиторий лежал в `~/Desktop/Vscode/google_workspace_mcp`) |
| `context7` | stdio | `./.mcp.json` (project-level, project1) | `npx -y @upstash/context7-mcp` | Актуальная документация библиотек/фреймворков |

Файлы конфига для копирования как есть (без секретов внутри них):
- `~/.mcp.json`
- `./.mcp.json` (в корне project1)

### claude.ai-коннекторы (НЕ требуют переноса — привязаны к аккаунту claude.ai, появятся сами на новой машине после входа в тот же аккаунт)
- claude.ai Firecrawl parsing
- claude.ai Google Calendar
- claude.ai Google Drive
- claude.ai Todoist
- claude.ai Canva — на момент снимка не авторизован, нужно подключить через claude.ai → Settings → Connectors
- claude.ai Gmail — на момент снимка не авторизован, нужно подключить через claude.ai → Settings → Connectors

---

## 2. CLAUDE.md

- `~/.claude/CLAUDE.md` (глобальный) — **отсутствовал** на исходной машине. Если нужен — создать заново.
- `./CLAUDE.md` (проектный, project1) — существует в репозитории, переносится вместе с git-клоном. Ничего отдельно делать не нужно.

---

## 3. Файловая память (`~/.claude/projects/*/memory/`)

Это **не в git** — живёт только на диске машины, где работал Claude Code. При переезде на новую машину папку `~/.claude/projects/` нужно скопировать целиком (или синхронизировать), иначе память начнётся с нуля.

На исходной машине было два каталога памяти:

**`-Users-che-Desktop-Vscode-project1/memory/`** (текущий проект):
MEMORY.md, feedback_autoexpert_bot_icon_autonomy.md, feedback_autoexpert_bot_translate_all.md, feedback_beginner_plain_explanations.md, goal_multi_gmail_connector.md, idea_telegram_parts_search_bot.md, project_autoexpert_client_app_idea.md, project_autoexpert_site_seo_rebuild.md, project_context7_superpowers_install.md, project_expedition_jimny_dream.md, project_motus_website_benchmark_goal.md, reference_aibasis_prompt_templates.md, user_email_identity.md

**`-Users-che/memory/`** (другой/старый путь проекта, `[INFERRED]` — вероятно тот же проект до переезда в `Desktop/Vscode/project1`):
MEMORY.md, autoexpert_motus_business.md, autoexpert_telegram_supplier_bot.md, feedback_actionable_links.md, feedback_gmail_declutter.md, feedback_memory_language.md, feedback_token_efficiency.md, google_tasks_lists.md, maserati_levante_parts_search.md, motus_crm_voice_bot_plan.md, project1_cross_machine_sync.md, project1_git_rules.md, project1_mission_roadmap.md, session_2026-07-28_greek_gym_grill.md, skroutz_receipts_print_workflow.md, todoist_project_structure.md, user_email_chegorx_rename.md, user_novice_tech_explanations.md

**Действие при переносе:** скопировать `~/.claude/projects/` целиком с исходной машины (rsync/архив), либо принять, что память начнётся заново.

---

## 4. Переменные окружения для MCP в settings.json

Проверены: `~/.claude/settings.json`, `./.claude/settings.json`, `./.claude/settings.local.json`.
**Ни в одном нет ключа `env`** — единственный ключ везде `permissions`. На новой машине переменные окружения для MCP через settings.json настраивать не требуется (их и не было).

---

## 5. Доступ к Google-сервисам — детали и что переносить

Два независимых пути авторизации:

### А) `workspace-mcp` (локальный сервер) — личный OAuth, файлы на диске
```
~/.google_workspace_mcp/credentials/
  <личный-gmail>.json
  <motus-business-gmail>.json
  <autoexpert-business-gmail-1>.json
  <autoexpert-business-gmail-2>.json
```
Это токены персонального OAuth (не сервисный аккаунт), по одному файлу на почтовый ящик — всего 4 ящика: 1 личный + 3 бизнес (Motus, AutoExpert×2). Реальные адреса не публикуются в этом файле — они видны в именах файлов на самом диске (`~/.google_workspace_mcp/credentials/`).

**Перенос — два варианта:**
1. Скопировать папку `~/.google_workspace_mcp/credentials/` защищённым способом (не через git, не через обычный облачный синк без шифрования) — тогда авторизация переедет вместе с файлами.
2. Не копировать и пройти OAuth заново на новой машине для каждого из 4 ящиков (дольше, но чище с точки зрения безопасности).

### Б) claude.ai-коннекторы (Gmail / Google Calendar / Google Drive)
Авторизация на стороне claude.ai через личный OAuth, к файлам машины не привязана. **Ничего переносить не нужно** — доступ действует на любой машине при входе в тот же аккаунт claude.ai. На момент снимка Gmail-коннектор не был авторизован — подключить отдельно.

---

## 6. Git remotes

Репозиторий `project1` синхронизируется с двумя remote:
- `origin` → `git@github.com:chegorx-blip/project1.git` (SSH)
- `gdrive` → `~/Library/CloudStorage/GoogleDrive-.../GitRepos/project1.git` (локальный путь к папке Google Drive этой машины)

**Перенос:**
- Для `origin` новой машине нужен свой SSH-ключ, привязанный к твоему GitHub-аккаунту — ключ не переносится через чат/копипаст, либо генерируешь новый и добавляешь его в GitHub, либо копируешь `~/.ssh/` защищённым способом.
- Для `gdrive` remote путь зависит от того, куда на новой машине смонтирован Google Drive (`git remote set-url gdrive <новый-путь>` после клонирования).
- На момент снимка на `origin` кроме `main` существует ветка `draft-b-spacious` — если она нужна, после клонирования сделать `git fetch --all`, чтобы она тоже подтянулась.

## 7. Настройки Claude Code (`settings.json`)

Помимо отсутствия `env`-переменных (см. п.4), сами файлы содержат `permissions` — правила разрешений на инструменты. Их стоит скопировать целиком, иначе на новой машине разрешения на инструменты придётся настраивать заново с нуля:
- `~/.claude/settings.json` (глобальные)
- `./.claude/settings.json` и `./.claude/settings.local.json` (проектные, project1 — второй файл обычно не в git, копировать отдельно)

---

## 8. Мульти-аккаунт Gmail (4 ящика) на втором локальном компьютере

**РЕШЕНО (2026-08-18), НЕ разворачивать:** второй компьютер — реальный Windows-ноутбук с локальным Claude Code (терминал VSCode), технически способен на то же самое, что и Mac. Но по решению пользователя остаёмся на раздельной схеме:
- `claude.ai Gmail` (привязан к аккаунту claude.ai, не к железу) — один общий ящик `chegorx@gmail.com`, виден одинаково в вебе, на Mac и на Windows.
- Остальные 3 ящика (Motus, AutoExpert×2) — **только на Mac** через `workspace-mcp`, не реплицируются на Windows.
- Вариант с общим VPS для всех 4 ящиков предложен и явно отклонён — избыточно на данный момент.

Инструкция ниже сохранена как справочная на случай, если решение пересмотрят.

---

Работает **только если на втором компьютере настоящий локальный Claude Code CLI**, не облачная/веб-сессия (у той нет доступа к портам/файлам — только встроенный коннектор claude.ai на 1 ящик).

Сервер: `taylorwilsdon/google_workspace_mcp` (PyPI-пакет `workspace-mcp`, Python 3.10+), поддерживает мультиаккаунты нативно.

### Инструкция — можно скопировать целиком и отдать локальному Claude на втором компьютере

```
1. Установить Python 3.10+ и пакет:
   pip install workspace-mcp

2. Создать файл .env в рабочей папке сервера с такими переменными
   (значения запросить у пользователя напрямую, НЕ через чат — это секреты):
   GOOGLE_OAUTH_CLIENT_ID=<спросить у пользователя>
   GOOGLE_OAUTH_CLIENT_SECRET=<спросить у пользователя>
   OAUTHLIB_INSECURE_TRANSPORT=1
   MCP_SINGLE_USER_MODE=1

3. Запустить сервер локально (порт 8000, как на исходной машине):
   workspace-mcp   # либо команда запуска, которую укажет README пакета

4. Прописать в ~/.mcp.json (на Windows — %USERPROFILE%\.mcp.json) файл:
   {
     "mcpServers": {
       "workspace-mcp": { "type": "http", "url": "http://localhost:8000/mcp" }
     }
   }

5. Авторизовать 4 почтовых ящика через OAuth в браузере — по одному,
   пока сервер запущен (каждый создаст свой JSON-файл в папке credentials).

6. Проверить: запросить у Claude на этой машине список доступных
   Google-аккаунтов через workspace-mcp — должно быть 4.
```

**Важно:** `GOOGLE_OAUTH_CLIENT_ID` / `GOOGLE_OAUTH_CLIENT_SECRET` — это секреты приложения, они не публикуются в этом файле и не пересылаются через чат. Их нужно взять напрямую с исходной машины (файл `~/Desktop/Vscode/google_workspace_mcp/.env`) и передать защищённым способом (менеджер паролей, зашифрованная передача) — не копипастом в переписку с ассистентом.

---

## Чек-лист для новой машины

- [ ] Склонировать репозиторий project1 (CLAUDE.md и `./.mcp.json` приедут автоматически)
- [ ] Скопировать `~/.mcp.json`
- [ ] Поднять `workspace-mcp` локально на порту 8000 (репозиторий сервера отдельно, не в этом проекте)
- [ ] Перенести или заново авторизовать `~/.google_workspace_mcp/credentials/` (4 ящика)
- [ ] Скопировать `~/.claude/projects/` для сохранения файловой памяти
- [ ] Войти в тот же аккаунт claude.ai — коннекторы (Calendar/Drive/Firecrawl/Todoist) подтянутся сами
- [ ] Авторизовать claude.ai Gmail и Canva коннекторы (были не подключены и на исходной машине)
- [ ] Настроить SSH-ключ для `origin` (GitHub) и поправить путь `gdrive` remote под новую машину
- [ ] `git fetch --all`, если нужна ветка `draft-b-spacious`
- [ ] Скопировать `~/.claude/settings.json` и проектные `settings.json`/`settings.local.json`
