import os
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase
from dotenv import load_dotenv

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")
if not DATABASE_URL:
    raise ValueError("DATABASE_URL environment variable is not set")

engine = create_async_engine(
    DATABASE_URL,
    echo=False,
    pool_size=10,  # 增加连接池大小
    max_overflow=15,  # 增加溢出连接数
    pool_recycle=1800,  # 30分钟回收连接
    pool_pre_ping=True,  # 使用前检测连接是否有效
    pool_timeout=10,  # 连接超时时间
    pool_use_lifo=True,  # LIFO 策略，保持连接温热
)
async_session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


class Base(DeclarativeBase):
    pass


async def get_session() -> AsyncSession:
    async with async_session() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
