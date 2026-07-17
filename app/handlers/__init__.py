from aiogram import Router

from app.handlers import help, quiz, results, start


def setup_routers() -> Router:
    root = Router(name="root")
    root.include_router(start.router)
    root.include_router(help.router)
    root.include_router(results.router)
    root.include_router(quiz.router)
    return root
