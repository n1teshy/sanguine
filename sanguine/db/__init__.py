import os

from peewee import SqliteDatabase

import sanguine.meta as meta
from sanguine.utils import app_dir

os.makedirs(app_dir, exist_ok=True)
db_file = os.path.join(app_dir, "db.db")
db = SqliteDatabase(db_file)
