# Telegram-бот для тестирования

Асинхронный Telegram-бот на **Python 3.11+** и **aiogram 3** с базой **SQLite**.

В базе хранится **150 вопросов**. Каждый тест выбирает **20 случайных** вопросов, перемешивает их и последовательно показывает пользователю. После завершения бот считает результат, процент и сохраняет историю.

## Возможности

- Главное меню: «Начать тест», «Мои результаты», «Помощь»
- Случайный выбор 20 уникальных вопросов из 150
- Inline-кнопки для вариантов ответа
- Подсчёт правильных/неправильных ответов и процента
- Просмотр ошибок после теста
- Статистика пользователя
- Продолжение незавершённого теста после перезапуска бота
- Импорт вопросов из JSON без дубликатов

## Структура проекта

```text
.
├── app/
│   ├── handlers/          # обработчики команд и кнопок
│   ├── keyboards/         # Reply и Inline клавиатуры
│   ├── database/          # модели, сессии, репозитории
│   ├── services/          # бизнес-логика теста и импорта
│   ├── middlewares/       # middleware сессии БД
│   ├── states/            # FSM-состояния
│   └── utils/             # логирование и тексты
├── data/
│   └── questions.json     # 150 вопросов
├── import_questions.py    # скрипт импорта
├── bot.py                 # точка входа
├── config.py              # настройки из .env
├── requirements.txt
├── .env.example
└── README.md
```

## 1. Установка Python

Нужен Python **3.11 или новее**.

### Linux / macOS

```bash
python3 --version
```

Если Python не установлен, установите его через сайт [python.org](https://www.python.org/downloads/) или пакетный менеджер системы.

### Windows

Скачайте установщик с [python.org](https://www.python.org/downloads/) и отметьте пункт **Add Python to PATH**.

Проверка:

```bash
python --version
```

## 2. Создание виртуального окружения

### Linux / macOS

```bash
python3 -m venv venv
source venv/bin/activate
```

### Windows

```bash
python -m venv venv
venv\Scripts\activate
```

## 3. Установка зависимостей

```bash
pip install -r requirements.txt
```

## 4. Получение токена через BotFather

1. Откройте Telegram и найдите [@BotFather](https://t.me/BotFather).
2. Отправьте команду `/newbot`.
3. Укажите имя и username бота.
4. Скопируйте выданный токен вида `123456:ABC-DEF...`.

## 5. Заполнение `.env`

Скопируйте пример:

```bash
cp .env.example .env
```

Откройте `.env` и укажите токен:

```env
BOT_TOKEN=ваш_токен_от_BotFather
DATABASE_URL=sqlite+aiosqlite:///quiz_bot.db
```

Токен нельзя хранить в исходном коде.

## 6. Создание базы данных

База создаётся автоматически при импорте вопросов и при запуске бота.

Таблицы:

- `users`
- `questions`
- `answer_options`
- `test_attempts`
- `attempt_questions`
- `user_answers`

## 7. Загрузка вопросов из JSON

Файл с вопросами: `data/questions.json`.

Импорт:

```bash
python import_questions.py
```

Скрипт:

1. Читает `questions.json`
2. Проверяет структуру
3. Требует минимум 2 варианта ответа
4. Требует ровно 1 правильный ответ
5. Добавляет вопросы в БД
6. Пропускает дубликаты при повторном запуске
7. Выводит количество загруженных и пропущенных вопросов

Другой файл:

```bash
python import_questions.py --file path/to/questions.json
```

## 8. Запуск бота

```bash
python bot.py
```

После запуска откройте бота в Telegram и отправьте `/start`.

## 9. Обновление списка вопросов

1. Отредактируйте `data/questions.json` или подготовьте новый файл.
2. Запустите `python import_questions.py`.
3. Уже существующие вопросы (с тем же текстом) не будут добавлены повторно.
4. Чтобы полностью заменить базу, удалите файл `quiz_bot.db` и выполните импорт заново.

Пример элемента JSON:

```json
[
  {
    "question": "Столица Российской Федерации?",
    "answers": [
      {"text": "Москва", "is_correct": true},
      {"text": "Санкт-Петербург", "is_correct": false},
      {"text": "Казань", "is_correct": false},
      {"text": "Новосибирск", "is_correct": false}
    ]
  }
]
```

## 10. Развёртывание на сервере

Рекомендуемый вариант — VPS с systemd.

1. Установите Python 3.11+.
2. Склонируйте репозиторий на сервер.
3. Создайте venv и установите зависимости.
4. Создайте `.env` с токеном.
5. Импортируйте вопросы.
6. Создайте unit-файл `/etc/systemd/system/quiz-bot.service`:

```ini
[Unit]
Description=Telegram Quiz Bot
After=network.target

[Service]
Type=simple
User=www-data
WorkingDirectory=/opt/quiz-bot
Environment=PYTHONUNBUFFERED=1
ExecStart=/opt/quiz-bot/venv/bin/python bot.py
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
```

Запуск:

```bash
sudo systemctl daemon-reload
sudo systemctl enable quiz-bot
sudo systemctl start quiz-bot
sudo systemctl status quiz-bot
```

Логи:

```bash
journalctl -u quiz-bot -f
```

## Команды быстрого старта

```bash
python -m venv venv
source venv/bin/activate          # Windows: venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env              # затем впишите BOT_TOKEN
python import_questions.py
python bot.py
```

## Оценка результата

- 90–100% — «Отличный результат!»
- 75–89% — «Хороший результат!»
- 50–74% — «Удовлетворительный результат»
- менее 50% — «Рекомендуем повторить материал»

Формула: `процент = правильные / 20 × 100`.

## Лицензия

Учебный проект. Используйте свободно для обучения и демонстраций.
