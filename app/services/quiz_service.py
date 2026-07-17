from __future__ import annotations

import logging
import random
from dataclasses import dataclass
from typing import Optional, Sequence

from sqlalchemy.ext.asyncio import AsyncSession

from app.database.models import AttemptQuestion, Question, TestAttempt, User, UserAnswer
from app.database.repositories import AttemptRepository, QuestionRepository, UserRepository
from config import get_settings

logger = logging.getLogger(__name__)

OPTION_LETTERS = ("А", "Б", "В", "Г", "Д", "Е")


@dataclass(slots=True)
class QuestionPayload:
    attempt_id: int
    question_id: int
    position: int
    total: int
    text: str
    options: list[tuple[int, str]]
    option_labels: list[str]


class QuizService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.users = UserRepository(session)
        self.questions = QuestionRepository(session)
        self.attempts = AttemptRepository(session)
        self.settings = get_settings(require_token=False)

    async def ensure_user(
        self,
        telegram_id: int,
        username: Optional[str],
        full_name: str,
    ) -> tuple[User, bool]:
        return await self.users.get_or_create(telegram_id, username, full_name)

    async def get_active_attempt(self, user_id: int) -> Optional[TestAttempt]:
        return await self.attempts.get_active_for_user(user_id)

    async def can_start_test(self, *, full: bool = False) -> bool:
        count = await self.questions.count_active()
        if full:
            return count >= 1
        return count >= self.settings.min_active_questions

    async def start_test(self, user: User, *, full: bool = False) -> TestAttempt:
        active = await self.get_active_attempt(user.id)
        if active is not None:
            raise RuntimeError("active_attempt_exists")

        if not await self.can_start_test(full=full):
            raise RuntimeError("not_enough_questions")

        all_questions = list(await self.questions.get_active_with_options())
        if full:
            selected = all_questions[:]
            random.shuffle(selected)
        else:
            selected = random.sample(
                all_questions,
                k=min(self.settings.questions_per_test, len(all_questions)),
            )
            random.shuffle(selected)

        question_ids = [question.id for question in selected]
        total_questions = len(question_ids)

        attempt = await self.attempts.create_attempt(
            user_id=user.id,
            question_ids=question_ids,
            total_questions=total_questions,
        )
        logger.info(
            "Начат тест attempt_id=%s user_id=%s mode=%s questions=%s",
            attempt.id,
            user.id,
            "killer" if full else "standard",
            total_questions,
        )
        return attempt

    async def restart_test(self, user: User, *, full: bool = False) -> TestAttempt:
        active = await self.get_active_attempt(user.id)
        if active is not None:
            await self.attempts.cancel_attempt(active)
            logger.info(
                "Отменён незавершённый тест attempt_id=%s user_id=%s",
                active.id,
                user.id,
            )
        return await self.start_test(user, full=full)

    @staticmethod
    def is_full_attempt(attempt: TestAttempt, questions_per_test: int) -> bool:
        return attempt.total_questions > questions_per_test

    async def get_current_question(self, attempt: TestAttempt) -> Optional[QuestionPayload]:
        if attempt.status != "in_progress":
            return None
        if attempt.current_index >= attempt.total_questions:
            return None

        ordered = sorted(attempt.questions, key=lambda item: item.position)
        if attempt.current_index >= len(ordered):
            return None

        current: AttemptQuestion = ordered[attempt.current_index]
        question = current.question
        if question is None or not question.is_active or not question.options:
            logger.error(
                "Вопрос недоступен attempt_id=%s question_id=%s",
                attempt.id,
                current.question_id,
            )
            return None

        options = [(option.id, option.option_text) for option in question.options]
        labels: list[str] = []
        short_options: list[tuple[int, str]] = []
        for index, (option_id, option_text) in enumerate(options):
            letter = OPTION_LETTERS[index] if index < len(OPTION_LETTERS) else str(index + 1)
            # If text already starts with "А. ", keep as is for message body.
            body_text = option_text
            labels.append(body_text)
            short_options.append((option_id, letter))

        return QuestionPayload(
            attempt_id=attempt.id,
            question_id=question.id,
            position=attempt.current_index + 1,
            total=attempt.total_questions,
            text=question.question_text,
            options=short_options,
            option_labels=labels,
        )

    async def submit_answer(
        self,
        attempt_id: int,
        question_id: int,
        option_id: int,
    ) -> tuple[str, Optional[TestAttempt], Optional[QuestionPayload]]:
        """
        Returns:
            status: ok | already_answered | stale | not_found | completed | missing_question
            attempt
            next_question (if any)
        """
        attempt = await self.attempts.get_by_id(attempt_id)
        if attempt is None or attempt.status != "in_progress":
            return "not_found", None, None

        current = await self.get_current_question(attempt)
        if current is None:
            return "missing_question", attempt, None

        if current.question_id != question_id:
            if await self.attempts.has_answer(attempt_id, question_id):
                return "already_answered", attempt, None
            return "stale", attempt, None

        option_ids = {option_id_ for option_id_, _ in current.options}
        if option_id not in option_ids:
            return "stale", attempt, None

        question = await self.questions.get_by_id(question_id)
        if question is None:
            return "missing_question", attempt, None

        selected = next((opt for opt in question.options if opt.id == option_id), None)
        if selected is None:
            return "stale", attempt, None

        answer = await self.attempts.save_answer(
            attempt=attempt,
            question_id=question_id,
            selected_option_id=option_id,
            is_correct=bool(selected.is_correct),
        )
        if answer is None:
            return "already_answered", attempt, None

        attempt = await self.attempts.get_by_id(attempt_id)
        if attempt is None:
            return "not_found", None, None

        if attempt.current_index >= attempt.total_questions:
            percentage = self.calculate_percentage(
                attempt.correct_answers,
                attempt.total_questions,
            )
            attempt = await self.attempts.complete_attempt(attempt, percentage)
            logger.info(
                "Тест завершён attempt_id=%s correct=%s percentage=%s",
                attempt.id,
                attempt.correct_answers,
                attempt.percentage,
            )
            return "completed", attempt, None

        next_question = await self.get_current_question(attempt)
        return "ok", attempt, next_question

    @staticmethod
    def calculate_percentage(correct: int, total: int) -> float:
        if total <= 0:
            return 0.0
        raw = (correct / total) * 100
        if raw == int(raw):
            return float(int(raw))
        return round(raw, 1)

    @staticmethod
    def grade_text(percentage: float) -> str:
        if percentage >= 90:
            return "Отличный результат!"
        if percentage >= 75:
            return "Хороший результат!"
        if percentage >= 50:
            return "Удовлетворительный результат"
        return "Рекомендуем повторить материал"

    @staticmethod
    def format_percentage(percentage: float) -> str:
        if percentage == int(percentage):
            return str(int(percentage))
        return str(percentage)

    async def get_wrong_answers(self, attempt_id: int) -> Sequence[UserAnswer]:
        return await self.attempts.get_wrong_answers(attempt_id)
