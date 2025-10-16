import os
import shutil
import stat
import textwrap

from colorama import Fore, Style
from colorama import init as colorama_init

import sanguine.meta as meta
from sanguine.utils import is_repo

colorama_init(autoreset=True)


def install():
    if not is_repo():
        print(f"{Fore.RED}Not a git repository.{Style.RESET_ALL}")
        return

    hooks_dir = ".git/hooks"
    hook_file = os.path.join(hooks_dir, "post-commit")
    os.makedirs(hooks_dir, exist_ok=True)

    py_exe = shutil.which("python")
    if py_exe:
        py_exe = py_exe.replace("\\", "/")

    script = textwrap.dedent(
        f"""\
        #!/bin/sh
        export FORCE_COLOR=1
        export TERM=xterm-256color

        PYTHON="{py_exe}"
        PREFIX=""

        if [ -x "$PYTHON" ]; then
            exec "$PYTHON" -m {meta.name} index
        elif command -v {meta.name} > /dev/null; then
            exec {meta.name} index
        else
            echo "{meta.name} not found"
            exit 1
        fi
        """
    )

    with open(hook_file, "w") as f:
        f.write(script)

    os.chmod(hook_file, os.stat(hook_file).st_mode | stat.S_IXUSR)
    print(f"{Fore.GREEN}{meta.name} has been installed!{Style.RESET_ALL}")


def uninstall():
    hook_file = ".git/hooks/post-commit"
    if os.path.exists(hook_file):
        os.remove(hook_file)
        print(
            f"{Fore.GREEN}{meta.name} has been uninstalled!{Style.RESET_ALL}"
        )
    else:
        print(f"{Fore.YELLOW}No hook found to uninstall.{Style.RESET_ALL}")
