![Python](https://img.shields.io/badge/python-3.10%2B-blue)
![License](https://img.shields.io/badge/license-MIT-green)
![YOLOv8](https://img.shields.io/badge/YOLOv8-Ultralytics-orange)

# DORES Pedestrian Flow — подсчёт пешеходного трафика

Модуль компьютерного зрения для подсчёта пешеходного потока на видео:
детекция людей, трекинг, подсчёт пересечений виртуальных линий и
формирование отчётов (JSON/CSV/график).

> **TL;DR.** Кладёте видео в `input/`, запускаете `make run` —
> получаете аннотированное видео, JSON-отчёт, CSV событий и график
> интенсивности в `output/`.

Проект на 100% написан AI.

---

## Содержание

- [Мотивация](#мотивация)
- [Что делает проект](#что-делает-проект)
- [Демо](#демо)
- [Технологический стек](#технологический-стек)
- [SWOT-анализ](#swot-анализ)
- [Быстрый старт](#быстрый-старт)
  - [Локально (Python)](#локально-python)
  - [Real-time (RTSP)](#real-time-rtsp)
- [Использование](#использование)
  - [Настройка виртуальных линий](#настройка-виртуальных-линий)
  - [Форматы отчётов](#форматы-отчётов)
- [Структура проекта](#структура-проекта)
- [Архитектура](#архитектура)
- [Требования](#требования)
- [Известные ограничения](#известные-ограничения)
- [Тесты](#тесты)
- [Как контрибьютить](#как-контрибьютить)
- [Авторы](#авторы)
- [Лицензия](#лицензия)
- [Благодарности](#благодарности)

---

## Мотивация

Существующие модули ДОРЕС (Детекция Объектов и Распознавание
Единиц Сценария) хорошо справляются с автомобильным трафиком, но
**пешеходный поток** остаётся слабо покрытым. При этом:

- пешеходные переходы — зона повышенного риска;
- интенсивность пешеходного трафика нужна для городского
  планирования, настройки светофоров, оценки загрузки улиц;
- готовые open-source решения (YOLO + DeepSORT/ByteTrack) хорошо
  отработаны, но требуют адаптации под конкретные ракурсы и качество
  видео ДОРЕС.

Проект демонстрирует, что задача **технически реализуема** и может
быть оформлена как расширение модуля ДОРЕС «Поток» без глубокой
интеграции с ИТС.

---

## Что делает проект

Пайплайн из трёх шагов:

1. **Детекция** — YOLOv8 (Ultralytics), класс `person` (class_id=0).
2. **Трекинг** — ByteTrack (через Ultralytics `model.track`),
   присваивает каждому пешеходу стабильный ID между кадрами.
3. **Подсчёт** — виртуальные линии: если трек пересекает заданный
   отрезок, счётчик увеличивается; направление определяется знаком
   векторного произведения.

Дополнительно:

- визуализация (bbox, ID, хвост трека, линия, HUD со счётчиками);
- аннотированное видео (`mp4`);
- JSON-отчёт с агрегированной статистикой и событиями;
- CSV со всеми событиями пересечений;
- график интенсивности (matplotlib) с адаптивным размером окна.

---

## Демо

После запуска в `output/` появятся:

| Файл | Что внутри |
|------|------------|
| `annotated.mp4` | видео с bbox, ID, линией и счётчиками |
| `report.json`  | агрегаты + список событий |
| `events.csv`   | построчный лог пересечений |
| `intensity.png`| столбчатый график интенсивности |

Пример фрагмента `report.json`:

```json
{
  "input_video": "input/crosswalk.mp4",
  "output_video": "output/annotated.mp4",
  "fps_avg": 24.7,
  "frames_processed": 1500,
  "duration_sec": 60.0,
  "bucket_sec": 5,
  "stats": {
    "total": 42,
    "per_line": { "line_main": { "in": 25, "out": 17 } }
  },
  "per_bucket": { "0": 5, "1": 7, "2": 4, "...": 0 },
  "events": [
    {
      "track_id": 12, "frame_idx": 87, "timestamp": 3.48,
      "direction": "in", "line_id": "line_main",
      "point": [980.5, 780.2]
    }
  ]
}
```

---

## Технологический стек

| Слой | Технология | Зачем |
|------|-----------|-------|
| Детекция | **YOLOv8** (Ultralytics) | быстрая и точная детекция людей, готовая интеграция с трекерами |
| Трекинг | **ByteTrack** (`bytetrack.yaml` из Ultralytics) | устойчив к перекрытиям (occlusion) — критично для улицы |
| Видео I/O | **OpenCV** (`cv2`) | чтение/запись видео, отрисовка |
| Численные операции | **NumPy** | работа с bbox, координатами |
| Визуализация графиков | **Matplotlib** | график интенсивности |
| Отчёты | stdlib `json`, `csv` | без лишних зависимостей |
| Язык | Python 3.10+ | современный синтаксис, `dataclass`, `from __future__ import annotations` |

**Почему ByteTrack, а не DeepSORT?** ByteTrack лучше держит
пешеходов при перекрытиях и не требует отдельной модели re-ID —
меньше зависимостей, проще демо.

---

## SWOT-анализ

| | Полезное | Вредное |
|---|---|---|
| **Внутреннее** | **Strengths:**<br>• простой и модульный пайплайн<br>• open-source стек без лицензионных ограничений<br>• работает offline, не требует интеграции с ДОРЕС<br>• адаптивные отчёты (JSON/CSV/график) | **Weaknesses:**<br>• точность зависит от качества видео и ракурса<br>• ночью/в сумерках деградация<br>• нет re-ID — при длительных перекрытиях треки теряются |
| **Внешнее** | **Opportunities:**<br>• расширение на мультикамеру<br>• интеграция с API ДОРЕС<br>• real-time на GPU<br>• подсчёт по зонам и тепловые карты | **Threats:**<br>• конкуренция с коммерческими VMS<br>• приватность (GDPR/152-ФЗ) при обработке видео людей<br>• дрейф качества данных с новых камер |

---

## Быстрый старт

### Локально (Python)

```bash
# 1. Клонировать
git clone https://github.com/Kole565/dores-pedestrian-plugin.git
cd dores-pedestrian-plugin

# 2. Виртуальное окружение
python3.10 -m venv .venv
source .venv/bin/activate          # Linux/macOS
# .venv\Scripts\activate           # Windows

# 3. Зависимости
pip install -r requirements.txt

# 4. Положить видео в input/
cp /path/to/your/video.mp4 input/

# 5. Запустить
python pipeline.py
```

Результаты — в `output/`.

### Real-time (RTSP)

Пайплайн умеет читать не только файлы, но и RTSP-потоки.
Для разработки и демо есть утилита, публикующая видеофайл как RTSP.

#### 1. Установить dev-зависимости

- **ffmpeg** в `PATH` — используется для публикации видео.
- **[MediaMTX](https://github.com/bluenviron/mediamtx/releases)** — лёгкий RTSP-сервер (распаковать и использовать вместе с конфигом).

```bash
# Debian/Ubuntu
sudo apt-get install -y ffmpeg
# macOS
#brew install ffmpeg

# MediaMTX: скачать бинарь под свою платформу
wget https://github.com/bluenviron/mediamtx/releases/download/v1.9.3/mediamtx_v1.9.3_linux_amd64.tar.gz
tar xzf mediamtx_v1.9.3_linux_amd64.tar.gz
```

#### 2. Запустить RTSP-сервер

```bash
# Терминал 1
./mediamtx
```

#### 3. Опубликовать видео в RTSP

```bash
# Терминал 2
./scripts/serve_rtsp.sh input/sample.mp4 --loop --port 8554
# Флаги: --loop, --fps, --bitrate, --port, --host, --path.
```

#### 4. Проверить, что поток читается

```bash
# Терминал 3
ffprobe -rtsp_transport tcp rtsp://localhost:8554/live
```

#### 5. Прогнать pipeline.py на RTSP

В config.py временно:

```python
INPUT_VIDEO = "rtsp://localhost:8554/live"
```

```bash
python pipeline.py
```

Что увидите:

HUD печатает Frame N (live) — счётчик кадров не имеет верхней границы;

если публикация прервётся, RTSPSource сам переподключится
с экспоненциальным backoff (в лог пойдут RTSP stale... reconnect);

остановка — Ctrl+C (мягкая, через stop_event).

---

## Использование

### Настройка виртуальных линий

Всё в `config.py`. Ключевой параметр — `VIRTUAL_LINES`:

```python
VIRTUAL_LINES = [
    {
        "line_id": "line_main",
        "coords": (960, 730, 1270, 840),  # x1, y1, x2, y2
        "direction_pos_to_neg": "in",
        "direction_neg_to_pos": "out",
        "use_point": "bottom_center",     # или "center"
    },
]
```

- `coords` — координаты отрезка в пикселях кадра.
- `direction_pos_to_neg` — как называть переход «слева направо»
  относительно направленного отрезка `(x1,y1)→(x2,y2)`.
- `use_point` — какая точка трека используется для проверки
  пересечения: `bottom_center` (по умолчанию, «под ногами») или
  `center`.

Несколько линий — просто добавьте элементы в список. Счётчики
ведутся отдельно по каждой `line_id`.

### Форматы отчётов

**JSON** (`output/report.json`) — агрегаты + события, удобно
парсить.

**CSV** (`output/events.csv`) — построчный лог:

```
frame_idx,timestamp,track_id,line_id,direction,px,py
87,3.480,12,line_main,in,980.5,780.2
```

**PNG** (`output/intensity.png`) — столбики по окнам; размер окна
подбирается автоматически (1, 2, 5, 10, …, 600 с) так, чтобы
получилось ~10 столбиков.

---

## Структура проекта

```
.
├── pipeline.py              # точка входа
├── config.py                # все настройки
├── sources/                 # источники видео
│   ├── base.py              # Protocol VideoSource
│   ├── file_source.py
│   ├── mot17_source.py      # Mot17Source dataset
│   ├── rtsp_source.py       # RTSPSource (reconnect, backoff, stale-check)
│   └── factory.py
├── counting/                # логика подсчёта пересечений
│   ├── counter.py
│   ├── factory.py
│   ├── geometry.py
│   └── types.py
├── tracking/
│   └── types.py             # Track — контракт между детекцией и подсчётом
├── reporting/
│   ├── report.py            # ReportBuilder + экспорт JSON/CSV
│   ├── plot.py              # график интенсивности
│   ├── video_writer.py      # AnnotatedVideoWriter
│   └── visualizer.py        # FrameVisualizer
├── tools/
│   └── video_to_rtsp.py     # dev-утилита: файл → RTSP (ffmpeg)
├── scripts/
│   └── serve_rtsp.sh
├── input/                   # сюда класть видео
├── output/                  # сюда пишутся результаты
├── models/                  # сюда скачиваются веса YOLO
├── Makefile
├── requirements.txt
└── README.md
```

---

## Архитектура

```
[Источник видео]                   [Сервер обработки]
 RTSP / файл ──► Video Capture ──► Детектор (YOLOv8)
                                          │
                                          ▼
                                   Трекер (ByteTrack)
                                          │
                                          ▼
                                   Модуль подсчёта (линии)
                                          │
                         ┌────────────────┴───────────────┐
                         ▼                                ▼
                   Визуализация (CV2)                 API / JSON
                   (annotated video)                 (результаты)
```

**Контракт между слоями** — `tracking.types.Track`. Любой трекер
(ByteTrack, DeepSORT, botsort) приводится к этому виду в
`pipeline.results_to_tracks`.

---

## Требования

### Минимальные (CPU-only, offline-обработка)

| Ресурс | Значение |
|--------|----------|
| CPU    | Intel i5 / Ryzen 5 |
| RAM    | 16 GB |
| Диск   | 20 GB (видео + модели) |
| Python | 3.10+ |
| OS     | Linux / macOS / Windows (WSL2) |

Ожидаемая скорость: **5–10 FPS** на `yolov8n` + ByteTrack на
современном CPU.

### Рекомендуемые (real-time)

| Ресурс | Значение |
|--------|----------|
| GPU    | NVIDIA GTX 1060+ (6 GB VRAM) |
| CUDA   | 11.8+ |
| RAM    | 16 GB |

Ожидаемая скорость: **30+ FPS** на `yolov8m`.

### Зависимости Python

См. `requirements.txt`, основные:

```
ultralytics>=8.2.0
opencv-python>=4.9.0
numpy>=1.26
matplotlib>=3.8
```

---

## Известные ограничения

- **`OPENCV_FFMPEG_CAPTURE_OPTIONS` — глобальная env-переменная.**
  `RTSPSource` выставляет её (TCP-транспорт + `stimeout`) перед созданием
  `cv2.VideoCapture`. Это влияет на все `cv2.VideoCapture` в процессе.
  Сейчас не проблема (один RTSP на процесс), но при переходе на
  многопоточный Stream Manager с несколькими RTSP потребуется замена
  на FFmpeg-pipeline-строку.

- **`pipeline.py` на live-источнике не завершается сам.**
  Остановка — `Ctrl+C` (через `SIGINT`-handler выставляется `stop_event`).
  Управляемая остановка появится в веб-бэкенде.

- **Координаты линий — в пикселях исходного кадра.**
  При смене разрешения видео конфиг линий нужно пересчитывать вручную.
  В веб-редакторе это будет автоматизировано.

- **Тесты отсутствуют.**
  Пока проект в демо-статусе, проверка — ручная, на коротких фрагментах
  с разными ракурсами.

---

## Тесты

На данный момент автоматические тесты не включены (демо-статус).
Планируется:

```bash
# после добавления тестов
pytest -q
```

Ручная проверка — на 5–10-секундных фрагментах с разными ракурсами.

---

## Как контрибьютить

1. Форкните репозиторий.
2. Создайте ветку: `git checkout -b feature/my-feature`.
3. Соблюдайте [Contributor Covenant](https://www.contributor-covenant.org/).
4. Перед PR прогоните `python pipeline.py` на тестовом видео.
5. В PR опишите: что меняется, зачем, как проверяли.

Правила сообщества — см.
[setting guidelines for repository contributors](https://docs.github.com/en/communities/setting-up-your-project-for-healthy-contributions/setting-guidelines-for-repository-contributors).

---

## Авторы

- **DeepSeek** — идея, реализация, документация.
- **Степанов Николай** — н̶а̶ п̶о̶д̶с̶о̶с̶е̶ соавтор.

---

## Лицензия

MIT License. См. файл [LICENSE](LICENSE).

---

## Благодарности

- [Ultralytics YOLOv8](https://github.com/ultralytics/ultralytics) — детекция и встроенные трекеры.
- [ByteTrack](https://github.com/ifzhang/ByteTrack) — алгоритм трекинга.
- [OpenCV](https://opencv.org/) — видео I/O и визуализация.
- [MOT17](https://motchallenge.net/data/MOT17/) — тестовые данные (+адаптер в `sources/mot17_source.py`).
- [Choose a License](https://choosealicense.com/) — за помощь с выбором лицензии.
- [Shields.io](https://shields.io) — за бейджи.
