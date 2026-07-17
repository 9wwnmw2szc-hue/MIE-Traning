from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional, Sequence

from sqlalchemy import Select, delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.database.models import (
    AnswerOption,
    AttemptQuestion,
    Question,
    TestAttempt,
    User,
    UserAnswer,
)


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class UserRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get_by_telegram_id(self, telegram_id: int) -> Optional[User]:
        result = await self.session.execute(
            select(User).where(User.telegram_id == telegram_id)
        )
        return result.scalar_one_or_none()

    async def get_or_create(
        self,
        telegram_id: int,
        username: Optional[str],
        full_name: str,
    ) -> tuple[User, bool]:
        user = await self.get_by_telegram_id(telegram_id)
        if user is not None:
            changed = False
            if user.username != username:
                user.username = username
                changed = True
            if user.full_name != full_name:
                user.full_name = full_name
                changed = True
            if changed:
                await self.session.flush()
            return user, False

        user = User(
            telegram_id=telegram_id,
            username=username,
            full_name=full_name,
        )
        self.session.add(user)
        await self.session.flush()
        return user, True


class QuestionRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def count_active(self) -> int:
        result = await self.session.execute(
            select(func.count()).select_from(Question).where(Question.is_active.is_(True))
        )
        return int(result.scalar_one())

    async def get_active_with_options(self) -> Sequence[Question]:
        result = await self.session.execute(
            select(Question)
            .where(Question.is_active.is_(True))
            .options(selectinload(Question.options))
            .order_by(Question.id)
        )
        return result.scalars().all()

    async def get_by_id(self, question_id: int) -> Optional[Question]:
        result = await self.session.execute(
            select(Question)
            .where(Question.id == question_id)
            .options(selectinload(Question.options))
        )
        return result.scalar_one_or_none()

    async def get_by_text(self, question_text: str) -> Optional[Question]:
        result = await self.session.execute(
            select(Question).where(Question.question_text == question_text)
        )
        return result.scalar_one_or_none()

    async def create_with_options(
        self,
        question_text: str,
        options: list[tuple[str, bool]],
    ) -> Question:
        question = Question(question_text=question_text, is_active=True)
        self.session.add(question)
        await self.session.flush()

        for option_text, is_correct in options:
            self.session.add(
                AnswerOption(
                    question_id=question.id,
                    option_text=option_text,
                    is_correct=is_correct,
                )
            )
        await self.session.flush()
        return question


class AttemptRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    def _base_query(self) -> Select[tuple[TestAttempt]]:
        return select(TestAttempt).options(
            selectinload(TestAttempt.questions).selectinload(AttemptQuestion.question).selectinload(
                Question.options
            ),
            selectinload(TestAttempt.answers).selectinload(UserAnswer.selected_option),
            selectinload(TestAttempt.answers).selectinload(UserAnswer.question).selectinload(
                Question.options
            ),
        )

    async def get_by_id(self, attempt_id: int) -> Optional[TestAttempt]:
        result = await self.session.execute(
            self._base_query()
            .where(TestAttempt.id == attempt_id)
            .execution_options(populate_existing=True)
        )
        return result.scalar_one_or_none()

    async def get_active_for_user(self, user_id: int) -> Optional[TestAttempt]:
        result = await self.session.execute(
            self._base_query()
            .where(
                TestAttempt.user_id == user_id,
                TestAttempt.status == "in_progress",
            )
            .order_by(TestAttempt.started_at.desc())
            .execution_options(populate_existing=True)
        )
        return result.scalar_one_or_none()

    async def has_answer(self, attempt_id: int, question_id: int) -> bool:
        result = await self.session.execute(
            select(UserAnswer.id).where(
                UserAnswer.attempt_id == attempt_id,
                UserAnswer.question_id == question_id,
            )
        )
        return result.scalar_one_or_none() is not None

    async def create_attempt(
        self,
        user_id: int,
        question_ids: Sequence[int],
        total_questions: int,
    ) -> TestAttempt:
        attempt = TestAttempt(
            user_id=user_id,
            total_questions=total_questions,
            current_index=0,
            status="in_progress",
            correct_answers=0,
            wrong_answers=0,
            percentage=0.0,
        )
        self.session.add(attempt)
        await self.session.flush()

        for position, question_id in enumerate(question_ids):
            self.session.add(
                AttemptQuestion(
                    attempt_id=attempt.id,
                    question_id=question_id,
                    position=position,
                )
            )
        await self.session.flush()
        return await self.get_by_id(attempt.id)  # type: ignore[return-value]

    async def cancel_attempt(self, attempt: TestAttempt) -> None:
        attempt.status = "cancelled"
        attempt.completed_at = utcnow()
        await self.session.flush()

    async def save_answer(
        self,
        attempt: TestAttempt,
        question_id: int,
        selected_option_id: int,
        is_correct: bool,
    ) -> UserAnswer | None:
        existing = await self.session.execute(
            select(UserAnswer).where(
                UserAnswer.attempt_id == attempt.id,
                UserAnswer.question_id == question_id,
            )
        )
        if existing.scalar_one_or_none() is not None:
            return None

        answer = UserAnswer(
            attempt_id=attempt.id,
            question_id=question_id,
            selected_option_id=selected_option_id,
            is_correct=is_correct,
        )
        self.session.add(answer)

        if is_correct:
            attempt.correct_answers += 1
        else:
            attempt.wrong_answers += 1

        attempt.current_index += 1
        await self.session.flush()
        return answer

    async def complete_attempt(self, attempt: TestAttempt, percentage: float) -> TestAttempt:
        attempt.status = "completed"
        attempt.percentage = percentage
        attempt.completed_at = utcnow()
        await self.session.flush()
        return attempt

    async def delete_attempt(self, attempt_id: int) -> None:
        await self.session.execute(
            delete(TestAttempt).where(TestAttempt.id == attempt_id)
        )
        await self.session.flush()

    async def get_completed_for_user(self, user_id: int) -> Sequence[TestAttempt]:
        result = await self.session.execute(
            select(TestAttempt)
            .where(
                TestAttempt.user_id == user_id,
                TestAttempt.status == "completed",
            )
            .order_by(TestAttempt.completed_at.desc())
        )
        return result.scalars().all()

    async def get_wrong_answers(self, attempt_id: int) -> Sequence[UserAnswer]:
        result = await self.session.execute(
            select(UserAnswer)
            .where(
                UserAnswer.attempt_id == attempt_id,
                UserAnswer.is_correct.is_(False),
            )
            .options(
                selectinload(UserAnswer.question).selectinload(Question.options),
                selectinload(UserAnswer.selected_option),
            )
            .order_by(UserAnswer.id)
        )
        return result.scalars().all()
