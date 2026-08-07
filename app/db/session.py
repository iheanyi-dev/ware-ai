from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.config import get_settings

settings = get_settings()

# psycopg (v3) has native asyncio support, so SQLAlchemy's async engine works
# with the same driver we use for sync tooling like Alembic — no need for a
# second driver like asyncpg. pool_pre_ping checks connections are alive
# before handing them out, avoiding stale-connection errors after idle time.
engine = create_async_engine(settings.database_url, echo=False, pool_pre_ping=True)

# async_sessionmaker is the async equivalent of sessionmaker. expire_on_commit=False
# means objects stay usable after commit() without triggering a fresh DB round-trip
# just to re-read attributes — important since our routes are async and we don't
# want surprise lazy-loads outside the session context.
AsyncSessionLocal = async_sessionmaker(bind=engine, expire_on_commit=False)


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """
    FastAPI dependency that yields an async database session and guarantees
    it's closed after the request finishes, even if an error is raised.

    Usage in an endpoint:
        @app.get("/something")
        async def endpoint(db: AsyncSession = Depends(get_db)):
            result = await db.execute(...)
    """
    async with AsyncSessionLocal() as session:
        yield session