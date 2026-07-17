from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.database.models import Base
from app.database.repositories import QuestionRepository

logger = logging.getLogger(__name__)


class ImportValidationError(ValueError):
    pass


def validate_question_item(item: Any, index: int) -> tuple[str, list[tuple[str, bool]]]:
    if not isinstance(item, dict):
        raise ImportValidationError(f"Элемент #{index + 1} должен быть объектом JSON.")

    question_text = item.get("question")
    if not isinstance(question_text, str) or not question_text.strip():
        raise ImportValidationError(f"Элемент #{index + 1}: отсутствует текст вопроса.")

    answers = item.get("answers")
    if not isinstance(answers, list) or len(answers) < 2:
        raise ImportValidationError(
            f"Элемент #{index + 1}: нужно минимум 2 варианта ответа."
        )
    if len(answers) > 6:
        raise ImportValidationError(
            f"Элемент #{index + 1}: допускается максимум 6 вариантов ответа."
        )

    options: list[tuple[str, bool]] = []
    correct_count = 0
    for answer_index, answer in enumerate(answers):
        if not isinstance(answer, dict):
            raise ImportValidationError(
                f"Элемент #{index + 1}, вариант #{answer_index + 1}: некорректный формат."
            )
        text = answer.get("text")
        is_correct = answer.get("is_correct")
        if not isinstance(text, str) or not text.strip():
            raise ImportValidationError(
                f"Элемент #{index + 1}, вариант #{answer_index + 1}: пустой текст."
            )
        if not isinstance(is_correct, bool):
            raise ImportValidationError(
                f"Элемент #{index + 1}, вариант #{answer_index + 1}: "
                "is_correct должен быть true/false."
            )
        if is_correct:
            correct_count += 1
        options.append((text.strip(), is_correct))

    if correct_count != 1:
        raise ImportValidationError(
            f"Элемент #{index + 1}: должен быть ровно один правильный ответ, "
            f"сейчас {correct_count}."
        )

    return question_text.strip(), options


class ImportService:
    def __init__(self, session: AsyncSession) -> None:
        self.questions = QuestionRepository(session)

    async def import_from_file(self, file_path: Path) -> tuple[int, int, list[str]]:
        if not file_path.exists():
            raise FileNotFoundError(f"Файл не найден: {file_path}")

        with file_path.open("r", encoding="utf-8") as file:
            payload = json.load(file)

        if not isinstance(payload, list):
            raise ImportValidationError("Корневой элемент JSON должен быть массивом.")

        imported = 0
        skipped = 0
        errors: list[str] = []

        for index, item in enumerate(payload):
            try:
                question_text, options = validate_question_item(item, index)
            except ImportValidationError as exc:
                skipped += 1
                errors.append(str(exc))
                logger.error("Ошибка импорта: %s", exc)
                continue

            existing = await self.questions.get_by_text(question_text)
            if existing is not None:
                skipped += 1
                continue

            await self.questions.create_with_options(question_text, options)
            imported += 1

        return imported, skipped, errors


async def run_import(
    database_url: str,
    questions_path: Path,
) -> tuple[int, int, list[str]]:
    engine = create_async_engine(database_url, echo=False, future=True)
    session_factory = async_sessionmaker(engine, expire_on_commit=False)

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    try:
        async with session_factory() as session:
            service = ImportService(session)
            imported, skipped, errors = await service.import_from_file(questions_path)
            await session.commit()
            return imported, skipped, errors
    finally:
        await engine.dispose()
