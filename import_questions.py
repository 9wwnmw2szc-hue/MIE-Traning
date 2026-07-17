from __future__ import annotations

import argparse
import asyncio
import logging
import sys
from pathlib import Path

from dotenv import load_dotenv

from app.services.import_service import ImportValidationError, run_import
from app.utils.logging import setup_logging
from config import get_database_url

ROOT = Path(__file__).resolve().parent
DEFAULT_QUESTIONS = ROOT / "data" / "questions.json"


async def _async_main(questions_path: Path, database_url: str) -> int:
    try:
        imported, skipped, errors = await run_import(database_url, questions_path)
    except FileNotFoundError as exc:
        logging.error("%s", exc)
        return 1
    except ImportValidationError as exc:
        logging.error("Файл вопросов некорректен: %s", exc)
        return 1
    except Exception:
        logging.exception("Ошибка импорта вопросов")
        return 1

    print(f"Успешно загружено: {imported}")
    print(f"Пропущено: {skipped}")
    if errors:
        print("Ошибки валидации:")
        for error in errors[:20]:
            print(f"  - {error}")
        if len(errors) > 20:
            print(f"  ... и ещё {len(errors) - 20}")
    return 0


def main() -> None:
    setup_logging()
    load_dotenv()

    parser = argparse.ArgumentParser(description="Импорт вопросов из JSON в SQLite")
    parser.add_argument(
        "--file",
        type=Path,
        default=DEFAULT_QUESTIONS,
        help="Путь к questions.json (по умолчанию data/questions.json)",
    )
    args = parser.parse_args()

    database_url = get_database_url()
    questions_path = args.file
    if not questions_path.is_absolute():
        questions_path = (ROOT / questions_path).resolve()

    raise SystemExit(asyncio.run(_async_main(questions_path, database_url)))


if __name__ == "__main__":
    main()
