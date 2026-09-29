# YAFR — Yet Another File Manager

CLI-организатор файлов для сортировки по расширениям и пакетного переименования: `1.jpg`, `2.jpg`, `S01E01.mkv`, `S01E02.mkv`.

**В разработке.** Реализованы Config, Engine и парсер CLI. Engine строит и выполняет планы сортировки и переименования через Python API. Команда `rename` пока только проверяет и выводит настройки — Engine к ней ещё не подключён.

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

## Engine

Планирование и просмотр не изменяют файловую систему. Для выполнения нужно явно передать `apply=True`:

```python
from yafr.engine import execute_plan, plan_rename

plan = plan_rename("./photos", pattern="{n:03d}", extensions=["jpg", "png"])
for operation in plan.operations:
    print(operation.source, "->", operation.destination)

report = execute_plan(plan)
# После проверки плана:
# report = execute_plan(plan, apply=True)
```

Сортировка по расширениям:

```python
from yafr.engine import plan_sort

plan = plan_sort(
    "./downloads",
    groups={"images": ["jpg", "png"], "archives": ["zip", "tar.gz"]},
    fallback="other",
)
```

- Файлы обрабатываются в естественном порядке: `file2` перед `file10`.
- Оба планировщика поддерживают `recursive`, `include_hidden` и `exclude`. Символические ссылки пропускаются. Путь используемого конфига нужно передать через `exclude`.
- Переименование поддерживает `{n}`, `{season}`, `{episode}` и дополнение нулями. Составные расширения можно задать через `known_extensions`.
- Сортировка поддерживает отдельный корень `output`. Без `fallback` неизвестные расширения остаются на месте.
- Конфликты и изменения источников проверяются перед выполнением. Перезапись существующего файла запрещена.

Ошибки планирования вызывают `PlanError`. Исполнение возвращает `ExecutionReport` со статусами операций; при ошибке останавливается и сохраняет сведения о частичном выполнении. Отката нет, созданные пустые каталоги могут остаться.

Перенос между файловыми системами, циклические переименования и смена только регистра не поддерживаются. Реальные операции проверены на macOS; Linux и Windows требуют отдельной проверки. План не блокирует файлы и каталоги от одновременных изменений другими процессами.

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

Готовый пример находится в `examples/config.toml`. Минимальная конфигурация:

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
| Engine | Поиск файлов, планирование, проверка конфликтов и выполнение | Реализован как Python API |
| App | Связывание слоёв и запуск сценариев | Точка входа — заглушка |

```text
src/yafr/
├── __init__.py          # Точка входа
├── cli/argparser.py     # Команды Typer
├── config/             # Загрузка, валидация и объединение настроек
└── engine/             # Поиск, планы, модели и исполнитель
tests/
├── test_argparser.py
├── test_config_service.py
├── test_config_validator.py
└── test_engine.py
```

## Разработка

```bash
uv run pytest -q
uv run ruff check .
uv run ruff format --check .
uv run mypy src
uv build
```

Тесты покрывают Config, CLI и Engine: приоритеты настроек, аргументы, порядок файлов, шаблоны, конфликты, сохранность содержимого и частичное выполнение. Только тесты Engine: `uv run pytest tests/test_engine.py -v`.

Следующие шаги: подключить CLI к точке входа и связать его с Engine через App, добавив просмотр и применение плана операций. Целевое поведение описано в `spec.md`.

## Лицензия

GNU GPLv3. Полный текст — в `LICENSE`.
