"""
Scan a repo such as https://github.com/os-autoinst/os-autoinst-distri-opensuse for tags
"""

import concurrent.futures
import fnmatch
import os
import re
from datetime import datetime, timedelta, timezone
from operator import itemgetter
from typing import Generator

from pygit2 import Repository  # type: ignore

from utils import utc_date

FILE_PATTERN = "*.pm"
LINE_PATTERN = (
    r"soft_fail.*?((?:bsc|poo)#[0-9]+|(?:gh|gl|gsd)#[^#]+#[0-9]+|jsc#[A-Z]+-[0-9]+)"
)


def git_blame(
    repo: Repository, file: str, line_number: int
) -> tuple[str, str, datetime]:
    """
    Get all the blame
    """
    blame = repo.blame(file, min_line=line_number, max_line=line_number).for_line(
        line_number
    )
    if "@" in blame.final_committer.email:
        name, email = blame.final_committer.name, blame.final_committer.email
    else:
        name, email = blame.final_committer.email, blame.final_committer.name
    tzone = timezone(timedelta(minutes=blame.final_committer.offset))
    date = datetime.fromtimestamp(blame.final_committer.time).replace(tzinfo=tzone)
    return name, email, date


def git_remote(repo: Repository) -> str | None:
    """
    Get remote
    """
    for remote in repo.remotes:
        if remote.name == "origin":
            url = remote.url
            if not url.startswith("https://") and "@" in url:
                url = url.split("@", 1)[1].replace(":", "/", 1)
                url = f"https://{url}"
            return url.rstrip("/").removesuffix(".git")
    return None


def recursive_grep(
    directory: str,
    pattern: str,
    file_pattern: str = "*",
    ignore_dirs: list[str] | None = None,
) -> Generator[tuple[str, int, str], None, None]:
    """
    Recursive grep
    """
    if ignore_dirs is None:
        ignore_dirs = []
    my_pattern = re.compile(pattern)
    for root, dirs, files in os.walk(directory):
        for ignore in set(ignore_dirs) & set(dirs):
            dirs.remove(ignore)
        for filename in files:
            if not fnmatch.fnmatch(filename, file_pattern):
                continue
            path = os.path.join(root, filename)
            with open(path, encoding="utf-8") as file:
                for line_number, line in enumerate(file, start=1):
                    for match in my_pattern.findall(line):
                        yield (path, line_number, match)


def scan_tags(directory: str = ".") -> dict[str, list[dict[str, str | int | datetime]]]:
    """
    Scan tags using multithreading without locking and by returning results from process_line
    """
    repo = Repository(directory)
    base_url = git_remote(repo)
    if base_url is not None:
        if "gitlab" in base_url:
            base_url = f"{base_url}/-"
        base_url = f"{base_url}/blob/{repo.head.shorthand}"

    def process_line(
        file: str, line_number: int, tag: str
    ) -> tuple[str, dict[str, str | int | datetime]]:
        author, email, date = git_blame(repo, file, line_number)
        info: dict[str, str | int | datetime] = {
            "file": file,
            "line_number": line_number,
            "author": author,
            "email": email,
            "date": utc_date(date),
            "url": f"{base_url}/{file}#L{line_number}",
        }
        return tag, info

    with concurrent.futures.ThreadPoolExecutor() as executor:
        futures = []
        for file, line_number, tag in recursive_grep(
            directory, LINE_PATTERN, FILE_PATTERN, ignore_dirs=[".git"]
        ):
            file = file.removeprefix(f"{directory}/")
            futures.append(executor.submit(process_line, file, line_number, tag))

        # Wait for all futures to complete and retrieve results
        results = [
            future.result() for future in concurrent.futures.as_completed(futures)
        ]

    # Group the results by tag in a dictionary
    tags: dict[str, list[dict[str, str | int | datetime]]] = {}
    for tag, info in results:
        if tag not in tags:
            tags[tag] = []
        tags[tag].append(info)
    for files in tags.values():
        files.sort(key=itemgetter("file", "line_number"))
    return tags
