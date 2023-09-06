#!/usr/bin/env python3
"""
Bugme
"""

import os
import json
import sys
from typing import List

from dateutil import parser
from pytz import utc

from github import Github, Auth, GithubException
from bugzilla import Bugzilla  # type: ignore
from bugzilla.exceptions import BugzillaError  # type: ignore

CREDENTIALS_FILE = os.path.expanduser("./creds.json")


def dateit(date: str = "", time_format: str = "%a %b %d %H:%M:%S %Z %Y") -> str:
    """
    Return date in desired format
    """
    return utc.normalize(parser.parse(date)).astimezone().strftime(time_format)


class GithubIssue:  # pylint: disable=too-few-public-methods
    """
    Simple class to hold GitHub issue
    """

    def __init__(self, repo: str, issue: str):
        self.repo = repo
        self.number = int(issue)


def main() -> None:
    """
    Main function
    """
    bsc_list: List[int] = []
    gh_list: List[GithubIssue] = []

    for arg in sys.argv[1:]:
        if arg.startswith(("bnc#", "boo#", "bsc#")):
            bsc_list.append(int(arg.split("#", 1)[1]))
        elif arg.startswith("gh#"):
            gh_list.append(GithubIssue(*arg.split("#", 2)[1:]))
        else:
            print(f"Unsupported {arg}", file=sys.stderr)

    with open(CREDENTIALS_FILE, encoding="utf-8") as file:
        if os.fstat(file.fileno()).st_mode & 0o77:
            sys.exit(f"ERROR: {CREDENTIALS_FILE} has insecure permissions")
        creds = json.load(file)

    # Bugzilla
    try:
        mybsc = Bugzilla("https://bugzilla.suse.com", force_rest=True, **creds["bugzilla.suse.com"])
        for bsc in mybsc.getbugs(bsc_list):
            print(f"bsc#{bsc.id}\t{bsc.status}\t{dateit(bsc.last_change_time)}\t{bsc.summary}")
        mybsc.disconnect()
    except BugzillaError as exc:
        print(f"bsc#{bsc.id}: {exc}")

    # Github
    auth = Auth.Token(**creds["github.com"])
    mygh = Github(auth=auth)
    for issue in gh_list:
        try:
            info = mygh.get_repo(issue.repo).get_issue(issue.number)
            print(f"gh#{info.number}\t{info.state}\t{dateit(info.last_modified)}\t{info.title}")
        except GithubException as exc:
            print(f"gh#{issue.repo}#{issue.number}: {exc}", file=sys.stderr)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        sys.exit(1)
