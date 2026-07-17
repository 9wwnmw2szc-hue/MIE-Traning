from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, Sequence

from sqlalchemy.ext.asyncio import AsyncSession

from app.database.models import TestAttempt
from app.database.repositories import AttemptRepository
from app.services.quiz_service import QuizService


@dataclass(slots=True)
class UserStats:
    total_tests: int
    last_percentage: float
    best_percentage: float
    average_percentage: float


class ResultService:
    def __init__(self, session: AsyncSession) -> None:
        self.attempts = AttemptRepository(session)

    async def get_user_stats(self, user_id: int) -> Optional[UserStats]:
        completed: Sequence[TestAttempt] = await self.attempts.get_completed_for_user(user_id)
        if not completed:
            return None

        percentages = [attempt.percentage for attempt in completed]
        return UserStats(
            total_tests=len(completed),
            last_percentage=completed[0].percentage,
            best_percentage=max(percentages),
            average_percentage=round(sum(percentages) / len(percentages), 1),
        )

    @staticmethod
    def format_stats(stats: UserStats) -> str:
        return (
            "Ваша статистика\n\n"
            f"Пройдено тестов: {stats.total_tests}\n"
            f"Последний результат: {QuizService.format_percentage(stats.last_percentage)}%\n"
            f"Лучший результат: {QuizService.format_percentage(stats.best_percentage)}%\n"
            f"Средний результат: {QuizService.format_percentage(stats.average_percentage)}%"
        )

    @staticmethod
    def format_finish_message(attempt: TestAttempt) -> str:
        percentage_text = QuizService.format_percentage(attempt.percentage)
        grade = QuizService.grade_text(attempt.percentage)
        return (
            "Тест завершён!\n\n"
            f"Правильных ответов: {attempt.correct_answers} из {attempt.total_questions}\n"
            f"Неправильных ответов: {attempt.wrong_answers}\n"
            f"Результат: {percentage_text}%\n\n"
            f"Оценка: {grade}"
        )
