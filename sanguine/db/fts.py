from typing import Optional

from playhouse.sqlite_ext import FTSModel, IntegerField, SearchField

import sanguine.constants as c
from sanguine.db import db
from sanguine.state import get_counter, update_counter

type_to_id = {c.ENTITY_VARIABLE: 1, c.ENTITY_FUNCTION: 2, c.ENTITY_CLASS: 3}
id_to_type = {v: k for k, v in type_to_id.items()}


class CodeEntity(FTSModel):
    id = IntegerField()
    type = IntegerField()
    file = SearchField()
    name = SearchField()

    class Meta:
        database = db


def fts_add_symbol(path: str, type: int, name: str) -> Optional[CodeEntity]:
    exists = (
        CodeEntity.select()
        .where(
            (CodeEntity.file == path)
            & (CodeEntity.name == name)
            & CodeEntity.type
            == type
        )
        .exists()
    )
    if exists:
        return

    update_counter()
    entity = CodeEntity.create(
        id=get_counter(),
        file=path,
        type=type,
        name=name,
    )
    return entity


def fts_remove_symbol(path: str, type: int, name: str) -> list[int]:
    query = CodeEntity.select(CodeEntity.id).where(
        (CodeEntity.file == path)
        & (CodeEntity.type == type)
        & (CodeEntity.name == name)
    )
    ids = [obj.id for obj in query]
    if ids:
        CodeEntity.delete().where(CodeEntity.id.in_(ids)).execute()
    return ids


def fts_remove_repo(path: str):
    CodeEntity.delete().where(CodeEntity.file.startswith(path)).execute()
