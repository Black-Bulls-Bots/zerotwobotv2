import asyncio
import importlib
import pkgutil
from pathlib import Path
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession, AsyncAttrs
from sqlalchemy.orm import DeclarativeBase
from zerotwo import DB_URI

class Base(AsyncAttrs, DeclarativeBase):
    pass

engine = create_async_engine(DB_URI, echo=False, pool_pre_ping=True)
async_session = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)

# Store startup hooks
_startup_hooks = []

# Dynamically import all modules in this package
_pkg_path = Path(__file__).parent
for _, module_name, is_pkg in pkgutil.iter_modules([str(_pkg_path)]):
    if not is_pkg and module_name != "__init__":
        module = importlib.import_module(f"{__name__}.{module_name}")
        # If module has startup() function, register it
        if hasattr(module, "startup") and callable(module.startup):
            _startup_hooks.append(module.startup)

async def init_db():
    # Create tables for all discovered models
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    # Run all startup hooks in parallel
    if _startup_hooks:
        await asyncio.gather(*(hook() for hook in _startup_hooks))
