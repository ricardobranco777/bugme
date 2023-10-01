"""
Scan a repo such as https://github.com/os-autoinst/os-autoinst-distri-opensuse for tags
"""

import concurrent.futures
import fnmatch
import logging
import os
import re
from collections import defaultdict
from datetime import datetime
from operator import itemgetter
from typing import Iterator

from github import Github  # , Auth
from dulwich.repo import Repo

from gitblame import GitBlame
from services import TAG_REGEX
from utils import utc_date

FILE_PATTERN = "*.pm"
LINE_REGEX = rf"soft_fail.*?({TAG_REGEX})"


def git_branch(repo: Repo) -> str:
    """
    Get branch
    """
    (_, ref), _ = repo.refs.follow(b"HEAD")
    return ref.decode("utf-8").split("/")[-1]


def git_remote(repo: Repo) -> str:
    """
    Get remote
    """
    url = repo.get_config().get(("remote", "origin"), "url").decode("utf-8")
    if not url.startswith("https://") and "@" in url:
        url = url.split("@", 1)[1].replace(":", "/", 1)
        url = f"https://{url}"
    return url.rstrip("/").removesuffix(".git")


def check_repo(repo: Repo, repo_name: str, branch: str, token: str) -> None:
    """
    Check repository
    """
    if repo.bare:
        raise RuntimeError(f"{repo.path} is bare")
    if not repo.has_index():
        raise RuntimeError(f"{repo.path} lacks index")
    last_commit = repo.head().decode("utf-8")
    # NOTE: Uncomment when latest PyGithub is published on Tumbleweed
    # auth = Auth.Token(**creds)
    # client = Github(auth=auth)
    client = Github(login_or_token=token)
    if (
        last_commit
        != client.get_repo(repo_name, lazy=True).get_branch(branch).commit.sha
    ):
        raise RuntimeError("Repo in filesystem and remote are not in sync")
    # NOTE: Remove exception handling when latest PyGithub is published on Tumbleweed
    try:
        client.close()
    except AttributeError:
        pass


def recursive_grep(
    directory: str,
    line_regex: str | re.Pattern,
    file_pattern: str = "*",
    ignore_dirs: list[str] | None = None,
) -> Iterator[tuple[str, int, str]]:
    """
    Recursive grep
    """
    if ignore_dirs is None:
        ignore_dirs = []
    line_regex = re.compile(line_regex)
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


def scan_tags(  # pylint: disable=too-many-locals
    directory: str, token: str
) -> dict[str, list[dict[str, str | int | datetime]]]:
    """
    Scan tags in repository
    """
    repo = Repo(directory)
    base_url = git_remote(repo)
    if "gitlab" in base_url:
        base_url = f"{base_url}/-"
    branch = git_branch(repo)
    owner_repo = base_url.split("/", 3)[-1]
    check_repo(repo, owner_repo, branch, token)
    blame = GitBlame(repo=owner_repo, branch=branch, access_token=token)

    def process_line(
        file: str, line_number: int, tag: str
    ) -> tuple[str, dict[str, str | int | datetime]]:
        try:
            author, email, commit, date = blame.blame_line(file, line_number)
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

    with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
        futures = []
        for file, line_number, tag in recursive_grep(
            directory,
            line_regex=LINE_REGEX,
            file_pattern=FILE_PATTERN,
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
