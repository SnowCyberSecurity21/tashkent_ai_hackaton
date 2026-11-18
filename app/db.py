"""Database engine and session helpers."""
from __future__ import annotations

import json
from functools import lru_cache
from typing import Iterator

from sqlmodel import Session, SQLModel, create_engine

from . import config

engine = create_engine(
    f"sqlite:///{config.DB_PATH.as_posix()}",
    connect_args={"check_same_thread": False},
)


def init_db() -> None:
    from . import models  # noqa: F401  (register tables)

    SQLModel.metadata.create_all(engine)


def get_session() -> Iterator[Session]:
    with Session(engine) as session:
        yield session


@lru_cache(maxsize=None)
def load_json(name: str):
    return json.loads((config.DATA_DIR / name).read_text(encoding="utf-8"))


def classes() -> dict[str, list[str]]:
    return load_json("classes.json")


def conditions() -> list[dict]:
    return load_json("conditions.json")


def condition_label(key: str) -> str:
    for c in conditions():
        if c["key"] == key:
            return c["label_uz"]
    return key.replace("_", " ").capitalize()
