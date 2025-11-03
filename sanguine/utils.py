import base64
import json
import os

import appdirs

import sanguine.meta as meta

app_dir = appdirs.user_data_dir(meta.name)
core_dir = os.path.dirname(__file__)

prog_lang_schema = json.load(
    open(os.path.join(core_dir, "assets", "prog_langs_schema.json"))
)
ext_to_lang = json.load(
    open(os.path.join(core_dir, "assets", "ext_to_lang.json"))
)


def is_repo():
    return os.path.exists(".git")


def normalize_path(path: str) -> str:
    path = os.path.abspath(os.path.expanduser(path))
    return path.replace(os.sep, "/").rstrip("/")


def encode_path(path: str) -> str:
    return base64.urlsafe_b64encode(path.encode()).decode()


def decode_path(name: str) -> str:
    return base64.urlsafe_b64decode(name.encode()).decode()
