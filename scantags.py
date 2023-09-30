"""
Scan a repo such as https://github.com/os-autoinst/os-autoinst-distri-opensuse for tags
"""

import concurrent.futures
import fnmatch
import logging
import os
import re
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from operator import itemgetter
from typing import Iterator

from pygit2 import Repository  # type: ignore

from services import TAG_REGEX
from utils import utc_date

FILE_PATTERN = "*.pm"
LINE_REGEX = rf"soft_fail.*?({TAG_REGEX})"


def git_blame(
    repo: Repository, file: str, line_number: int
) -> tuple[str, str, str, datetime]:
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
    return name, email, blame.final_commit_id, date


def git_remote(repo: Repository) -> str:
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
    return ""


def check_repo(repo: Repository) -> None:
    """
    Check repo health
    """
    if repo.is_bare:
        raise RuntimeError(f"{repo.path} is bare")
    if repo.is_empty:
        raise RuntimeError(f"{repo.path} is emtpy")
    if repo.is_shallow:
        raise RuntimeError(f"{repo.path} is shallow")
    if repo.head_is_detached:
        raise RuntimeError(f"{repo.path} HEAD is detached")
    if repo.head_is_unborn:
        raise RuntimeError(f"{repo.path} HEAD is unborn")


def recursive_grep(
    directory: str,
    line_regex: str | re.Pattern,
    file_pattern: str = "*",
    ignore_case: bool = False,
    ignore_dirs: list[str] | None = None,
) -> Iterator[tuple[str, int, str]]:
    """
    Recursive grep
    """
    if ignore_dirs is None:
        ignore_dirs = []
    line_regex = re.compile(line_regex, flags=re.IGNORECASE if ignore_case else 0)
    for root, dirs, files in os.walk(directory):
        for ignore in set(ignore_dirs) & set(dirs):
            dirs.remove(ignore)
        for filename in files:
            if not fnmatch.fnmatch(filename, file_pattern):
                continue
            filename = os.path.join(root, filename)
            try:
                with open(filename, encoding="utf-8") as file:
                    for line_number, line in enumerate(file, start=1):
                        for match in line_regex.findall(line):
                            yield (filename, line_number, match)
            except UnicodeError:
                pass


def scan_tags(directory: str = ".") -> dict[str, list[dict[str, str | int | datetime]]]:
    """
    Scan tags using multithreading without locking and by returning results from process_line
    """
    repo = Repository(directory)
    check_repo(repo)
    base_url = git_remote(repo)
    if "gitlab" in base_url:
        base_url = f"{base_url}/-"
    branch = repo.head.shorthand

    def process_line(
        file: str, line_number: int, tag: str
    ) -> tuple[str, dict[str, str | int | datetime]]:
        try:
            author, email, commit, date = git_blame(repo, file, line_number)
        except KeyError as exc:
            logging.warning("%s: %s: %s: %s", file, line_number, tag, exc)
            return tag, {}
        info: dict[str, str | int | datetime] = {
            "file": file,
            "line_number": line_number,
            "author": author,
            "email": email,
            "date": utc_date(date),
            "commit": f"{base_url}/commit/{commit}",
            "url": f"{base_url}/blob/{branch}/{file}#L{line_number}",
        }
        return tag, info

    with concurrent.futures.ThreadPoolExecutor() as executor:
        futures = []
        for file, line_number, tag in recursive_grep(
            directory,
            line_regex=LINE_REGEX,
            file_pattern=FILE_PATTERN,
            ignore_case=True,
            ignore_dirs=[".git", "t"],
        ):
            file = file.removeprefix(f"{directory}/")
            futures.append(executor.submit(process_line, file, line_number, tag))

        # Wait for all futures to complete and retrieve results
        results = [
            future.result() for future in concurrent.futures.as_completed(futures)
        ]

    # Group the results by tag in a dictionary
    tags: dict[str, list[dict[str, str | int | datetime]]] = defaultdict(list)
    for tag, info in results:
        if not info:
            continue
        # build.opensuse.org & bugzilla.novell.com -> bugzilla.suse.com
        if tag.startswith(("bnc", "boo")):
            tag = tag.replace("boo", "bsc").replace("bnc", "bsc")
        tags[tag].append(info)
    for files in tags.values():
        files.sort(key=itemgetter("file", "line_number"))
    return tags
