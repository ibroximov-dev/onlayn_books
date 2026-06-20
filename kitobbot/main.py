import asyncio
import logging
from aiogram import Bot, Dispatcher
from aiogram.fsm.storage.memory import MemoryStorage

from config import BOT_TOKEN
from database.db import init_db
from handlers import start, books, audio, tests, timer, rating, certificates, admin, tales # type: ignore


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)


logger = logging.getLogger(__name__)



async def main():
    bot = Bot(token=BOT_TOKEN)
    storage = MemoryStorage()
    dp = Dispatcher(storage=storage)


    dp.include_router(start.router)
    dp.include_router(books.router)
    dp.include_router(audio.router)
    dp.include_router(tests.router)
    dp.include_router(timer.router)
    dp.include_router(rating.router)
    dp.include_router(certificates.router)
    dp.include_router(tales.router)
    dp.include_router(admin.router)



    await init_db()
    logger.info("✅Database tayyor")

    logger.info("🚀Bot ishga tushdi!")

if __name__ == "__main__":
    asyncio.run(main())