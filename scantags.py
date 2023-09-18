"""
Scan a repo such as https://github.com/os-autoinst/os-autoinst-distri-opensuse for tags
"""

import contextlib
import fnmatch
import logging
import os
import re
from typing import Generator

from dulwich.repo import Repo

FILE_PATTERN = "*.pm"
LINE_PATTERN = (
    r"soft_fail.*?((?:bsc|poo)#[0-9]+|(?:gh|gl|gsd)#[^#]+#[0-9]+|jsc#[A-Z]+-[0-9]+)"
)


def git_branch(directory: str = ".") -> str:
    """
    Get current git branch
    """
    with Repo(directory) as repo:
        (_, ref), _ = repo.refs.follow(b"HEAD")
        return os.path.basename(ref.decode("utf-8"))


def git_remote(directory: str = ".") -> str:
    """
    Get git remote
    """
    with Repo(directory) as repo:
        output = repo.get_config().get(("remote", "origin"), "url").decode("utf-8")
    if output.startswith(("git@", "gitlab@")):
        output = re.sub(
            "^git(?:lab)?@", "https://", output.replace(":", "/", 1), count=1
        )
    return output.rstrip("/").removesuffix(".git")


def recursive_grep(
    directory: str,
    pattern: str,
    file_pattern: str = "*",
) -> Generator[tuple[str, str, str], None, None]:
    """
    Recursive grep
    """
    my_pattern = re.compile(pattern)
    for root, dirs, files in os.walk(directory):
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
        base_url = git_remote(directory)
        if base_url is not None:
            base_url = (
                f"{base_url}/-/blob" if "gitlab" in base_url else f"{base_url}/blob"
            )
            branch = git_branch(directory)
            base_url = f"{base_url}/{branch}"
        for file, line_number, tag in recursive_grep(
            directory, LINE_PATTERN, FILE_PATTERN
        ):
            file = file.removeprefix(f"{directory}/")
            if tag not in tags:
                tags[tag] = []
            tags[tag].append(
                {
                    "file": file,
                    "lineno": line_number,
                    "url": f"{base_url}/{file}#L{line_number}",
                }
            )
        return tags
