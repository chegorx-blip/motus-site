# windows-workspace-mcp-setup.ps1
#
# Запускать ТОЛЬКО в настоящем локальном Windows Terminal / PowerShell
# (не в VSCode-терминале, если тот подключён к облачному контейнеру —
#  проверка встроена ниже и остановит скрипт, если это не так).
#
# Что делает: клонирует workspace-mcp, создаёт .env (пустые секреты —
# их вписываешь сам вручную), безопасно дополняет .mcp.json, ничего
# не перезаписывает молча. Ничего не запускает и не трогает Google —
# сервер и OAuth ты запускаешь отдельно, последней командой, которую
# скрипт выведет в конце.

$ErrorActionPreference = "Stop"

Write-Host "=== Проверка окружения ===" -ForegroundColor Cyan

# 0. Убедиться, что это реально Windows, а не облачный Linux-контейнер
if ($env:OS -notlike "*Windows*") {
    Write-Host "СТОП: это не похоже на настоящий Windows. env:OS = $($env:OS)" -ForegroundColor Red
    Write-Host "Похоже, это снова облачная/контейнерная среда. Скрипт остановлен." -ForegroundColor Red
    exit 1
}
Write-Host "OK: реальная Windows-среда ($env:COMPUTERNAME)" -ForegroundColor Green

# 1. Python
try {
    $pyVersion = python --version 2>&1
    Write-Host "OK: Python найден -> $pyVersion" -ForegroundColor Green
} catch {
    Write-Host "СТОП: Python не найден в PATH." -ForegroundColor Red
    Write-Host "Поставь Python 3.10+ с https://python.org/downloads (отметь 'Add to PATH' при установке) и запусти скрипт заново." -ForegroundColor Yellow
    exit 1
}

# 2. git
try {
    $gitVersion = git --version 2>&1
    Write-Host "OK: git найден -> $gitVersion" -ForegroundColor Green
} catch {
    Write-Host "СТОП: git не найден в PATH." -ForegroundColor Red
    Write-Host "Поставь Git с https://git-scm.com/download/win и запусти скрипт заново." -ForegroundColor Yellow
    exit 1
}

# 3. uv (менеджер окружений Python — так же запущено на исходной машине)
try {
    $uvVersion = uv --version 2>&1
    Write-Host "OK: uv уже установлен -> $uvVersion" -ForegroundColor Green
} catch {
    Write-Host "Ставлю uv..." -ForegroundColor Cyan
    pip install uv
    Write-Host "OK: uv установлен" -ForegroundColor Green
}

Write-Host ""
Write-Host "=== Репозиторий сервера ===" -ForegroundColor Cyan

$repoPath = Join-Path $env:USERPROFILE "workspace-mcp"

if (Test-Path $repoPath) {
    Write-Host "Папка уже существует: $repoPath — обновляю (git pull)" -ForegroundColor Yellow
    git -C $repoPath pull
} else {
    Write-Host "Клонирую в $repoPath ..." -ForegroundColor Cyan
    git clone https://github.com/taylorwilsdon/google_workspace_mcp.git $repoPath
}

Write-Host ""
Write-Host "=== Файл .env ===" -ForegroundColor Cyan

$envPath = Join-Path $repoPath ".env"

if (Test-Path $envPath) {
    Write-Host "Файл .env уже существует, НЕ трогаю его: $envPath" -ForegroundColor Yellow
    Write-Host "Открой его сам и проверь, что там 4 строки: GOOGLE_OAUTH_CLIENT_ID, GOOGLE_OAUTH_CLIENT_SECRET, OAUTHLIB_INSECURE_TRANSPORT, MCP_SINGLE_USER_MODE" -ForegroundColor Yellow
} else {
    $envContent = @"
GOOGLE_OAUTH_CLIENT_ID=
GOOGLE_OAUTH_CLIENT_SECRET=
OAUTHLIB_INSECURE_TRANSPORT=1
MCP_SINGLE_USER_MODE=1
"@
    Set-Content -Path $envPath -Value $envContent -Encoding UTF8
    Write-Host "Создан пустой .env (секреты нужно вписать вручную): $envPath" -ForegroundColor Green
}

Write-Host ""
Write-Host "=== Файл .mcp.json ===" -ForegroundColor Cyan

$mcpJsonPath = Join-Path $env:USERPROFILE ".mcp.json"
$workspaceMcpEntry = @{
    type = "http"
    url  = "http://localhost:8000/mcp"
}

if (Test-Path $mcpJsonPath) {
    Write-Host "Файл уже существует: $mcpJsonPath — читаю и дополняю, не перезаписываю целиком" -ForegroundColor Yellow
    $raw = Get-Content -Path $mcpJsonPath -Raw
    try {
        $json = $raw | ConvertFrom-Json
    } catch {
        Write-Host "СТОП: не смог разобрать существующий .mcp.json как JSON — он повреждён или не JSON." -ForegroundColor Red
        Write-Host "Содержимое файла:" -ForegroundColor Yellow
        Write-Host $raw
        Write-Host "Поправь файл вручную и запусти скрипт заново, либо допиши workspace-mcp в mcpServers сам." -ForegroundColor Yellow
        exit 1
    }

    if (-not $json.mcpServers) {
        $json | Add-Member -MemberType NoteProperty -Name "mcpServers" -Value ([PSCustomObject]@{}) -Force
    }
    if ($json.mcpServers.PSObject.Properties.Name -contains "workspace-mcp") {
        Write-Host "В файле уже есть запись 'workspace-mcp' — оставляю как есть, ничего не меняю." -ForegroundColor Yellow
    } else {
        $json.mcpServers | Add-Member -MemberType NoteProperty -Name "workspace-mcp" -Value $workspaceMcpEntry
        ($json | ConvertTo-Json -Depth 10) | Set-Content -Path $mcpJsonPath -Encoding UTF8
        Write-Host "Добавлена запись 'workspace-mcp' в существующий .mcp.json, остальное содержимое сохранено." -ForegroundColor Green
    }
} else {
    $fresh = @{ mcpServers = @{ "workspace-mcp" = $workspaceMcpEntry } }
    ($fresh | ConvertTo-Json -Depth 10) | Set-Content -Path $mcpJsonPath -Encoding UTF8
    Write-Host "Создан новый .mcp.json: $mcpJsonPath" -ForegroundColor Green
}

Write-Host ""
Write-Host "=== ГОТОВО ===" -ForegroundColor Cyan
Write-Host "Папка сервера: $repoPath" -ForegroundColor White
Write-Host "Файл секретов (впиши туда 2 значения вручную из Telegram Избранного): $envPath" -ForegroundColor White
Write-Host ""
Write-Host "Дальше, ПОСЛЕ того как впишешь секреты в .env:" -ForegroundColor Cyan
Write-Host "  cd `"$repoPath`"" -ForegroundColor White
Write-Host "  uv run main.py --transport streamable-http" -ForegroundColor White
Write-Host "  (НЕ 'uv run workspace-mcp' — та команда стартует в режиме stdio, не HTTP, и workspace-cli к ней не подключится)" -ForegroundColor Yellow
Write-Host ""
Write-Host "Это запустит сервер на localhost:8000 и откроет в браузере авторизацию Google по очереди для каждого добавляемого ящика." -ForegroundColor White
