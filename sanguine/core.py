import difflib
import os
import subprocess
import sys
from functools import reduce
from typing import Optional

import pathspec
from colorama import Fore, Style
from tqdm import tqdm

import sanguine.constants as c
import sanguine.git as git
import sanguine.meta as meta
from sanguine.db import db
from sanguine.db.fts import (
    CodeEntity,
    fts_add_symbol,
    fts_remove_symbol,
    id_to_type,
    type_to_id,
)
from sanguine.db.hnsw import hnsw_add_symbol, hnsw_remove_symbol, hnsw_search
from sanguine.parser import extract_symbols
from sanguine.state import get_staleness, update_staleness
from sanguine.utils import ext_to_lang, is_repo


def index_diff(file_diff: dict[str, tuple[str, Optional[str]]]):
    for file, (added_lines, removed_lines) in tqdm(
        file_diff.items(),
        total=len(file_diff),
        ncols=80,
        bar_format=f"{Fore.GREEN}[{meta.name}] |{{bar}}|{Style.RESET_ALL}",
    ):
        ext = os.path.splitext(file)[1]
        if ext not in ext_to_lang:
            continue

        file_path = os.path.abspath(file)
        lang = ext_to_lang[ext]

        added_symbols = extract_symbols(added_lines, lang)
        removed_symbols = {c.FLD_FUNCTIONS: [], c.FLD_CLASSES: []}
        if removed_lines:
            removed_symbols = extract_symbols(removed_lines, lang)

        with db.atomic():
            for entity_type, field_name in [
                (c.ENTITY_FUNCTION, c.FLD_FUNCTIONS),
                (c.ENTITY_CLASS, c.FLD_CLASSES),
            ]:
                for symbol_name in added_symbols[field_name]:
                    o = fts_add_symbol(
                        path=file_path,
                        type=type_to_id[entity_type],
                        name=symbol_name,
                    )
                    hnsw_add_symbol([symbol_name], [o.id])

                for symbol_name in removed_symbols[field_name]:
                    ids = fts_remove_symbol(
                        file_path, type_to_id[entity_type], symbol_name
                    )
                    for id in ids:
                        hnsw_remove_symbol(id)
    print()


def process_commit(commit_id: Optional[str] = None):
    if not is_repo():
        print(
            f"{Fore.RED}Error: not a git repository.{Style.RESET_ALL}",
            file=sys.stderr,
        )
        return

    try:
        commit = commit_id or git.last_commit()
        file_to_diff = git.commit_diff(commit)
        index_diff(file_to_diff)
    except subprocess.CalledProcessError:
        print(
            f"{Fore.RED}Invalid commit ID{Style.RESET_ALL}",
            file=sys.stderr,
        )


def index_file(file: str):
    if not os.path.isfile(file):
        print(
            f"{Fore.RED}{file} is not a file{Style.RESET_ALL}",
            file=sys.stderr,
        )
        return
    with open(file, encoding="utf-8") as f:
        index_diff({file: (f.read(), "")})


def index_all_files():
    cwd = os.getcwd()
    ignore_file = os.path.join(cwd, ".gitignore")
    patterns = []
    if os.path.exists(ignore_file):
        with open(ignore_file, "r") as f:
            patterns = f.read().splitlines()

    spec = pathspec.PathSpec.from_lines("gitwildmatch", patterns)
    file_diff = {}

    for dirpath, dirnames, filenames in os.walk(cwd):
        if ".git" in dirnames:
            dirnames.remove(".git")
        dirnames[:] = [d for d in dirnames if not d.startswith(".")]

        for name in filenames:
            if name.startswith("."):
                continue

            filepath = os.path.relpath(os.path.join(dirpath, name), cwd)
            if spec.match_file(filepath):
                continue

            try:
                with open(filepath) as f:
                    file_diff[filepath] = (f.read(), "")
            except (UnicodeDecodeError, PermissionError):
                continue

    if not file_diff:
        print(f"{Fore.YELLOW}No indexable files found.{Style.RESET_ALL}")
        return

    index_diff(file_diff)


def search(
    query: str,
    k: int,
    path: Optional[str] = None,
    type: Optional[str] = None,
    show_score: bool = True,
):
    conditions = [CodeEntity.name.contains(query)]
    if path is not None:
        path = os.path.abspath(path)
        conditions.append(CodeEntity.file.startswith(path))
    if type is not None:
        type = type_to_id[type]
        conditions.append(CodeEntity.type == type)

    conditions = reduce(lambda x, y: x & y, conditions)
    db_objects = CodeEntity.select().where(conditions)
    db_map = {o.id: o for o in db_objects}

    total_hnsw_no, stale_hnsw_no = 0, 0
    sim_ids, sim_scores = hnsw_search(query, k=k)
    total_hnsw_no += len(sim_ids)
    sim_score_map = dict(zip(sim_ids, sim_scores))
    sim_map = {
        o.id: o for o in CodeEntity.select().where(CodeEntity.id.in_(sim_ids))
    }
    stale_hnsw_no += len(sim_ids) - len(sim_map)
    sim_ids = set(sim_ids)

    if len(sim_map) < k / 2:
        more_ids, more_scores = hnsw_search(query, k=k * 2)
        for s_id, score in zip(more_ids, more_scores):
            if s_id in sim_ids:
                continue
            total_hnsw_no += 1
            s_o = CodeEntity.get_or_none(id=s_id)
            if s_o is None:
                stale_hnsw_no += 1
                continue
            sim_ids.add(s_id)
            sim_score_map[s_id] = score
            sim_map[s_id] = s_o

    update_staleness(total_hnsw_no, stale_hnsw_no)
    staleness = get_staleness()

    if staleness > 0.5:
        print(
            f"{Fore.YELLOW}HNSW needs index refreshing, >50% entries are stale. Bordering uselessness.{Style.RESET_ALL}"
        )
    elif staleness > 0.3:
        print(
            f"{Fore.YELLOW}HNSW needs rindex efreshing, >30% entries are stale.{Style.RESET_ALL}"
        )
    if staleness > 0.3:
        print(f'run "{meta.name} refresh" to refresh\n')

    all_ids = list(sim_ids) + [o.id for o in db_objects if o.id not in sim_ids]
    results = []
    for oid in all_ids:
        obj = sim_map.get(oid) or db_map.get(oid)
        if obj is None or (type is not None and obj.type != type):
            continue
        sim_score = sim_score_map.get(oid, 0)
        text_score = difflib.SequenceMatcher(
            None, query.lower(), obj.name.lower()
        ).ratio()
        final_score = sim_score + text_score
        results.append((obj, final_score))

    results.sort(key=lambda x: x[1], reverse=True)
    results = results[:k]

    if not results:
        print("No matches found.")
        return

    last_file = results[0][0].file
    for obj, score in results:
        if obj.file != last_file:
            print()
            print(f"{Fore.CYAN}{obj.file}{Style.RESET_ALL}")

        color = (
            Fore.GREEN
            if id_to_type[obj.type] == c.ENTITY_FUNCTION
            else Fore.BLUE
        )
        line = f"  {color}↳ {obj.name}{Style.RESET_ALL}"
        if show_score:
            line += f" ({score:.2f})"
        print(line)
        last_file = obj.file

    print()


def delete(
    name: Optional[str] = None,
    path: Optional[str] = None,
    type: Optional[str] = None,
    force: bool = False,
):
    conditions = []
    if name:
        conditions.append(CodeEntity.name.startswith(name))
    if path:
        path = os.path.abspath(path)
        conditions.append(CodeEntity.file.startswith(path))
    if type:
        conditions.append(CodeEntity.type == type_to_id[type])

    if not conditions:
        print(
            f"{Fore.YELLOW}No criteria provided for deletion.{Style.RESET_ALL}"
        )
        return

    query = CodeEntity.select().where(reduce(lambda x, y: x & y, conditions))
    total_no = query.count()

    if total_no == 0:
        print("No matching entities found for deletion.")
        return

    if force:
        with db.atomic():
            for obj in query:
                deleted_ids = fts_remove_symbol(obj.file, obj.type, obj.name)
                for _id in deleted_ids:
                    hnsw_remove_symbol(_id)
        print(f"{Fore.GREEN}{total_no} entities deleted.{Style.RESET_ALL}")
        return

    while True:
        print(
            f"{Fore.YELLOW}Warning: {total_no} entities match the criteria!{Style.RESET_ALL}"
        )
        choice = (
            input("Type 'yes' or 'y' to delete, 'list' to preview entities: ")
            .strip()
            .lower()
        )

        if choice in {"yes", "y"}:
            with db.atomic():
                for obj in query:
                    deleted_ids = fts_remove_symbol(
                        obj.file, obj.type, obj.name
                    )
                    for _id in deleted_ids:
                        hnsw_remove_symbol(_id)
            print(f"{Fore.GREEN}{total_no} entities deleted.{Style.RESET_ALL}")
            break

        elif choice == "list":
            print(
                f"{Fore.CYAN}Listing all matching entities:{Style.RESET_ALL}"
            )
            for obj in query:
                color = (
                    Fore.GREEN
                    if id_to_type[obj.type] == c.ENTITY_FUNCTION
                    else Fore.BLUE
                )
                print(f"{color}↳ {obj.name}{Style.RESET_ALL} in {obj.file}")
            print()

        else:
            print("\nDeletion cancelled.")
            break
