"""
Scan a repo such as https://github.com/os-autoinst/os-autoinst-distri-opensuse for tags
"""

import contextlib
import fnmatch
import logging
import os
import re
import shlex
import subprocess
from typing import Generator

FILE_PATTERN = "*.pm"
LINE_PATTERN = r"soft_fail.*?((?:bsc|poo)#[0-9]+|(?:gh|gl|gsd)#[^#]+#[0-9]+)"


def git_blame(file: str, line_number: str) -> str:
    """
    Run git blame and return the e-mail
    """
    if not line_number.isdigit():
        raise ValueError(f"Invalid number: {line_number}")
    cmd = f"git blame --porcelain -L {line_number},{line_number} {file}"
    try:
        output = subprocess.check_output(
            shlex.split(cmd), shell=False, universal_newlines=True
        ).strip()
    except subprocess.CalledProcessError as exc:
        logging.error("%s: %s", file, exc)
        return "UNKNOWN"
    for line in output.splitlines():
        if "@" in line:
            return line.split()[1]
    return "UNKNOWN"


def git_branch() -> str:
    """
    Get current branch
    """
    cmd = "git symbolic-ref --short HEAD"
    try:
        return subprocess.check_output(
            shlex.split(cmd), shell=False, universal_newlines=True
        ).strip()
    except subprocess.CalledProcessError as exc:
        logging.error("%s: %s", cmd, exc)
    return "master"


def git_remote() -> str | None:
    """
    Get most likely remote
    """
    cmd = "git remote get-url upstream"
    try:
        output = subprocess.check_output(
            shlex.split(cmd),
            shell=False,
            stderr=subprocess.DEVNULL,
            universal_newlines=True,
        ).strip()
    except subprocess.CalledProcessError:
        cmd = "git remote get-url origin"
        try:
            output = subprocess.check_output(
                shlex.split(cmd),
                shell=False,
                stderr=subprocess.DEVNULL,
                universal_newlines=True,
            ).strip()
        except subprocess.CalledProcessError as exc:
            logging.error("%s: %s", cmd, exc)
            return None
    if output.startswith(("git@", "gitlab@")):
        output = re.sub(
            "^git(?:lab)?@", "https://", output.replace(":", "/", 1), count=1
        )
    return output.rstrip("/").removesuffix(".git")


def recursive_grep(
    directory: str,
    pattern: str,
    file_pattern: str = "*",
    ignore_dirs: list[str] | None = None,
) -> Generator[tuple[str, str, str], None, None]:
    """
    Recursive grep
    """
    if ignore_dirs is None:
        ignore_dirs = []
    my_pattern = re.compile(pattern)
    for root, dirs, files in os.walk(directory):
        for ignore in ignore_dirs:
            if ignore in dirs:
                dirs.remove(ignore)
        dirs.sort()
        files.sort()
        for filename in files:
            if not fnmatch.fnmatch(filename, file_pattern):
                continue
            path = os.path.join(root, filename)
            with open(path, encoding="utf-8") as file:
                for line_number, line in enumerate(file, start=1):
                    for match in my_pattern.findall(line):
                        yield (path, str(line_number), match)


def scan_tags(directory: str = ".") -> dict[str, list[dict[str, str]]]:
    """
    Scan tags
    """
    tags: dict[str, list[dict[str, str]]] = {}

    with contextlib.chdir(directory):
        if not os.path.isdir(os.path.join(directory, ".git")):
            logging.error("ERROR: No git repo in %s", directory)
            return {}
        base_url = git_remote()
        if base_url is not None:
            base_url = (
                f"{base_url}/-/blob" if "gitlab" in base_url else f"{base_url}/blob"
            )
            branch = git_branch()
            base_url = f"{base_url}/{branch}"
        for file, line_number, tag in recursive_grep(
            directory, LINE_PATTERN, FILE_PATTERN, ignore_dirs=[".git"]
        ):
            author = git_blame(file, line_number)
            file = file.removeprefix(f"{directory}/")
            if tag not in tags:
                tags[tag] = []
            tags[tag].append(
                {
                    "file": file,
                    "lineno": line_number,
                    "author": author,
                    "url": f"{base_url}/{file}#L{line_number}",
                }
            )
        return tags
