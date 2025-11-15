import argparse
import os
import sys

import sanguine.constants as c
import sanguine.meta as meta


def main():
    global_parser = argparse.ArgumentParser(add_help=False)
    global_parser.add_argument(
        "--cuda", action="store_true", help="Use GPU to run embedding model"
    )
    global_parser.add_argument(
        "--version",
        "-v",
        action="version",
        version=f"%(prog)s {meta.version}",
        help="Show version and exit",
    )

    parser = argparse.ArgumentParser(
        prog=meta.name,
        description=f"Keep it D.R.Y with {meta.name}.",
        formatter_class=lambda prog: argparse.HelpFormatter(
            prog, max_help_position=25, width=120
        ),
        usage=argparse.SUPPRESS,
        parents=[global_parser],
    )

    subparsers = parser.add_subparsers(
        dest="command", help="Available commands"
    )

    subparsers.add_parser(
        "install", help="Install post-commit hook", parents=[global_parser]
    )
    subparsers.add_parser(
        "uninstall", help="Uninstall post-commit hook", parents=[global_parser]
    )
    subparsers.add_parser(
        "ls", help="List indexed repositories", parents=[global_parser]
    )

    index_parser = subparsers.add_parser(
        "index", help="Index code", parents=[global_parser]
    )
    index_parser.add_argument(
        "--commit-id",
        "-c",
        type=str,
        help="Specific commit ID to index (defaults to last commit)",
    )
    index_parser.add_argument(
        "--file",
        "-f",
        type=str,
        help="Specific file to index",
    )
    index_parser.add_argument(
        "--all-files",
        "-a",
        action="store_true",
        help="Index all files in current folder not ignored by .gitignore",
    )

    search_parser = subparsers.add_parser(
        "search", help="Search indexed code", parents=[global_parser]
    )
    search_parser.add_argument(
        "text", type=str, nargs="?", help="Search query"
    )
    search_parser.add_argument(
        "--count", "-k", type=int, default=10, help="Number of results"
    )
    search_parser.add_argument(
        "--interactive",
        "-i",
        action="store_true",
        help="Interactive (REPL) search",
    )
    search_parser.add_argument(
        "--path", "-p", type=str, help="Filter by path prefix"
    )
    search_parser.add_argument(
        "--type",
        "-t",
        type=str,
        choices=[c.ENTITY_CLASS, c.ENTITY_FUNCTION],
        help="Filter by code entity type",
    )

    delete_parser = subparsers.add_parser(
        "delete", help="Delete indexed entities", parents=[global_parser]
    )
    delete_parser.add_argument(
        "--name",
        "-n",
        type=str,
        help="Name or partial name of entities to delete",
    )
    delete_parser.add_argument(
        "--path", "-p", type=str, help="Path prefix to filter entities"
    )
    delete_parser.add_argument(
        "--type",
        "-t",
        type=str,
        choices=[c.ENTITY_CLASS, c.ENTITY_FUNCTION],
        help="Filter by entity type",
    )
    delete_parser.add_argument(
        "--yes", "-y", type=str, help="Delete without asking"
    )

    subparsers.add_parser(
        "refresh", help="Refresh the embedding index", parents=[global_parser]
    )

    args = parser.parse_args(sys.argv[1:] or ["-h"])

    # --- imports here, so '--help' doesn't do any heavy-lifting ---
    from colorama import Fore, Style
    from colorama import init as colorama_init

    from sanguine.db import db
    from sanguine.db.fts import CodeEntity
    from sanguine.install_uninstall import install, uninstall

    colorama_init(autoreset=True)

    if db.is_closed():
        db.connect()
    db.create_tables([CodeEntity], safe=True)

    from sanguine.core import (
        delete,
        index_all_files,
        index_file,
        process_commit,
        search,
    )
    from sanguine.db.hnsw import (
        indices_dir,
        init_hnsw,
        refresh_hnsw_index,
        save_indices,
    )
    from sanguine.utils import decode_path

    if args.command == "install":
        install()
        return

    if args.command == "uninstall":
        uninstall()
        return

    if args.command == "ls":
        for path in os.listdir(indices_dir):
            print(decode_path(path))
        return

    init_hnsw(use_cuda=args.cuda)

    if args.command == "index":
        if args.file:
            index_file(args.file)
        elif args.all_files:
            index_all_files()
        else:
            process_commit(args.commit_id)

        save_indices()
        return

    if args.command == "search":
        if not args.interactive:
            if not args.text:
                print("Search text is required unless using --interactive")
                sys.exit(1)
            search(args.text, k=args.count, path=args.path, type=args.type)
            return
        print("Interactive search. Type ':q' to quit.")
        while True:
            cmd = input(">> ").strip()
            if cmd.lower() == ":q":
                break
            parts = cmd.split()
            if not parts:
                continue
            kwargs = search_parser.parse_args(parts)
            search(
                kwargs.text, k=kwargs.count, path=kwargs.path, type=kwargs.type
            )
        return

    if args.command == "delete":
        if not args.name and not args.path:
            print(
                f"{Fore.RED}Error: You must provide at least --name or --path for deletion.{Style.RESET_ALL}"
            )
            sys.exit(1)
        delete(
            name=args.name, path=args.path, type=args.type, confirmed=args.yes
        )
        save_indices()
        return

    if args.command == "refresh":
        refresh_hnsw_index()
        return

    parser.print_help()
    sys.exit(1)
