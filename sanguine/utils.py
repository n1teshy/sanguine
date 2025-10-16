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
