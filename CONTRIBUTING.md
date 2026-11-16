# Разработка YT

Используйте Windows x64 и Python 3.13. Node.js 22+ и Inno Setup нужны для сборки установщика.

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.lock.txt
.\.venv\Scripts\python.exe -m pip install --no-deps --no-build-isolation -e .
```

Установка editable подключает `src/yt` к окружению: изменения доступны без переустановки.
Для разработки с обновлёнными зависимостями вместо lock-файла: `pip install -e ".[dev,build]"`.

```powershell
.\.venv\Scripts\python.exe -m yt
.\.venv\Scripts\python.exe -m ruff check .
.\.venv\Scripts\python.exe -m ruff format --check .
.\.venv\Scripts\python.exe -m pytest -q
```

Для автоформатирования — `python -m ruff format .`. Быстрый прогон без GUI —
`python -m pytest -q -m "not desktop"`. Полные GUI-сценарии требуют рабочего стола Windows;
они изолированы по процессам. Тесты аудио используют беззвучный SDL-драйвер.

Сначала ознакомьтесь с [архитектурой](docs/ARCHITECTURE.md). Изменение сценария
воспроизведения обычно затрагивает `application/playback.py` и тесты плеера.
Изменение оформления — `presentation/`. Новая интеграция добавляется как адаптер
`infrastructure/` и подключается в `bootstrap.py`.

Не передавайте виджеты в фоновые задачи. Для UI-событий используйте `AppEvent` и
`EventKind`. Сохраняйте совместимость пользовательских настроек и архива загрузок.
Не храните состояние сеанса в глобальных переменных модулей.

Все визуальные ассеты хранятся в `public/`. Инструкция экспорта иконки —
[public/icon-design.md](public/icon-design.md). Установщик использует ICO с именем,
содержащим хеш, чтобы Windows не показывала старую иконку из кэша.

## Зависимости и релиз

Основной список зависимостей — `pyproject.toml`; `requirements.lock.txt` фиксирует
полное окружение разработки и сборки, включая dev-инструменты. После осознанного
обновления в чистом окружении пересоздайте lock:

```powershell
python -m pip install -e ".[dev,build]"
python -m pip freeze --exclude-editable > requirements.lock.txt
```

Сохраняйте lock-файл в UTF-8 (Windows PowerShell 5 перенаправляет вывод в UTF-16;
для него используйте `scripts/lock_dependencies.py`). Не добавляйте локальную editable-ссылку в lock.

Перед релизом обновите `VERSION` и `CHANGELOG.md`, переустановите editable-пакет,
выполните проверки и `release.cmd`. Тег GitHub должен совпадать с версией, например `v1.0.0`.
Автоматизация описана в [README](README.md).
