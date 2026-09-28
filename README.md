# YAFR — Yet Another File Manager

CLI-организатор файлов для сортировки по расширениям и пакетного переименования: `1.jpg`, `2.jpg`, `S01E01.mkv`, `S01E02.mkv`.

**В разработке.** Реализованы конфигурация и CLI-команда `rename`, которая проверяет и выводит настройки. Перемещение, переименование файлов и построение плана операций пока не реализованы.

## Запуск

Требования: Python 3.12+ и uv. Команды выполняются из корня проекта.

Код использует `platformdirs`, но зависимость пока отсутствует в `pyproject.toml`. Для установки в чистом окружении:

```bash
uv add 'platformdirs>=4,<5'
uv sync --locked
```

Точка входа `yafr` пока выводит приветствие. Запустить текущий CLI можно напрямую:

```bash
uv run python -c 'from yafr.cli.argparser import cli; cli()' --help
uv run python -c 'from yafr.cli.argparser import cli; cli()' rename ./photos --pattern '{n:03d}' --start 1
```

Каталог `./photos` должен существовать. Команда показывает исходный путь и итоговые настройки; файлы не изменяются.

## CLI

```text
rename SOURCE [OPTIONS]
```

| Параметр | Назначение |
| --- | --- |
| `SOURCE` | Существующий исходный каталог |
| `--config PATH` | Путь к TOML-конфигурации |
| `--pattern TEXT` | Шаблон имени, например `{n:03d}` |
| `--start INTEGER` | Начальный номер, не меньше 1 |
| `--recursive / --no-recursive` | Включить или выключить рекурсию в настройках |
| `--help` | Справка |

Неуказанные параметры сохраняют значения из конфигурации. Ошибки аргументов и настроек выводятся в stderr с кодом завершения `2`. Команды `sort` и флага `--apply` пока нет.

## Конфигурация

Приоритет: **явные параметры CLI → TOML → встроенные значения**.

Минимальный `config.toml`:

```toml
version = 1

[general]
recursive = false
include_hidden = false

[rename]
pattern = "S{season:02d}E{episode:02d}"
start = 1
season = 1
```

Передайте файл через `--config config.toml`. Без этого параметра используется `config.toml` из пользовательского каталога настроек, определённого `platformdirs` для `yafr`. Если стандартного файла нет, используются встроенные значения; отсутствие явно указанного файла считается ошибкой.

Config также поддерживает `sort.output`, `sort.fallback` и `sort.groups`. Пользовательская таблица групп заменяет встроенную целиком. Расширения задаются без начальной точки; повторы и неизвестные поля запрещены. Относительный `sort.output` из файла считается от его каталога, из переопределений — от рабочего каталога.

Python API:

```python
from yafr.config import load_config

config = load_config("config.toml", overrides={"rename": {"start": 5}})
print(config.rename.pattern)
```

`load_config()` возвращает модель `Config`, не создаёт файлов и сообщает об ошибках через `ConfigError`.

## Архитектура

| Слой | Назначение | Состояние |
| --- | --- | --- |
| CLI | Разбор аргументов и вывод результата | `rename` на Typer |
| Config | Чтение TOML, валидация Pydantic, приоритеты настроек | Реализован |
| Engine | Планирование и выполнение файловых операций | Планируется |
| App | Связывание слоёв и запуск сценариев | Точка входа — заглушка |

```text
src/yafr/
├── __init__.py          # Точка входа
├── cli/argparser.py     # Команды Typer
└── config/
    ├── __init__.py      # Публичный API
    ├── loader.py        # Чтение TOML
    ├── validator.py     # Модели и проверки
    └── service.py       # Загрузка и объединение настроек
tests/
├── test_argparser.py
├── test_config_service.py
└── test_config_validator.py
```

## Разработка

```bash
uv run pytest -q
uv run ruff check .
uv run ruff format --check .
uv run mypy src
uv build
```

Тесты покрывают конфигурацию, приоритеты CLI, справку, некорректные аргументы, ошибки и отсутствие изменений файлов при просмотре. Для запуска только тестов CLI: `uv run pytest tests/test_argparser.py -v`.

Следующие шаги: подключить CLI к точке входа, реализовать Engine и добавить просмотр и применение плана операций. Целевое поведение описано в `spec.md`.
