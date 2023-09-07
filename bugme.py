#!/usr/bin/env python3
"""
Bugme
"""

import os
import json
import sys

from dateutil import parser
from pytz import utc

from github import Github, Auth, GithubException
from gitlab import Gitlab
from gitlab.exceptions import GitlabError
from bugzilla import Bugzilla
from bugzilla.exceptions import BugzillaError
from redminelib import Redmine
from redminelib.exceptions import BaseRedmineError

CREDENTIALS_FILE = os.path.expanduser("~/creds.json")


def dateit(date, time_format: str = "%a %b %d %H:%M:%S %Z %Y") -> str:
    """
    Return date in desired format
    """
    if isinstance(date, str):
        date = utc.normalize(parser.parse(date))
    return date.astimezone().strftime(time_format)


def do_bugzilla(url: str, bugs: list, creds):
    """
    Bugzilla
    """
    if len(bugs) == 0:
        return
    try:
        mybugz = Bugzilla(url, force_rest=True, **creds)
        for bug in mybugz.getbugs(bugs):
            print(f"bsc#{bug.id}\t{bug.status}\t\t{dateit(bug.last_change_time)}\t{bug.summary}")
        mybugz.disconnect()
    except BugzillaError as exc:
        print(f"Bugzilla: {exc}")


def do_github(issues: list, creds: dict):
    """
    Github
    """
    if len(issues) == 0:
        return
    auth = Auth.Token(**creds)
    mygh = Github(auth=auth)
    for issue in issues:
        try:
            info = mygh.get_repo(issue.repo, lazy=True).get_issue(issue.number)
            print(f"gh#{info.number}\t{info.state}\t\t{dateit(info.last_modified)}\t{info.title}")
        except GithubException as exc:
            print(f"gh#{issue.repo}#{issue.number}: {exc}", file=sys.stderr)


def do_gitlab(url: str, issues: list, creds: dict):
    """
    Gitlab
    """
    if len(issues) == 0:
        return
    with Gitlab(url=url, **creds) as mygl:
        for issue in issues:
            try:
                info = mygl.projects.get(issue.repo, lazy=True).issues.get(issue.number)
                print(f"gl#{info.iid}\t{info.state}\t\t{dateit(info.updated_at)}\t{info.title}")
            except GitlabError as exc:
                print(f"gl#{issue.repo}#{issue.number}: {exc}", file=sys.stderr)


def do_redmine(url: str, tickets: list, creds: dict):
    """
    Redmine
    """
    if len(tickets) == 0:
        return
    redmine = Redmine(url=url, raise_attr_exception=False, **creds)
    for ticket in tickets:
        try:
            info = redmine.issue.get(ticket)
            print(f"poo#{info.id}\t{info.status}\t{dateit(info.updated_on)}\t{info.subject}")
        except BaseRedmineError as exc:
            print(f"poo#{ticket}: {exc}", file=sys.stderr)


class RepoIssue:  # pylint: disable=too-few-public-methods
    """
    Simple class to hold GitHub issue
    """

    def __init__(self, repo: str, issue: str):
        self.repo = repo
        self.number = int(issue)


def main():
    """
    Main function
    """
    bsc_list = []
    poo_list = []
    gh_list = []
    gl_list = []
    gsd_list = []

    for arg in sys.argv[1:]:
        if arg.startswith(("bnc#", "boo#", "bsc#")):
            bsc_list.append(int(arg.split("#", 1)[1]))
        elif arg.startswith("poo#"):
            poo_list.append(int(arg.split("#", 1)[1]))
        elif arg.startswith("gh#"):
            gh_list.append(RepoIssue(*arg.split("#", 2)[1:]))
        elif arg.startswith("gl#"):
            gl_list.append(RepoIssue(*arg.split("#", 2)[1:]))
        elif arg.startswith("gsd#"):
            gsd_list.append(RepoIssue(*arg.split("#", 2)[1:]))
        else:
            print(f"Unsupported {arg}", file=sys.stderr)

    with open(CREDENTIALS_FILE, encoding="utf-8") as file:
        if os.fstat(file.fileno()).st_mode & 0o77:
            sys.exit(f"ERROR: {CREDENTIALS_FILE} has insecure permissions")
        creds = json.load(file)

    do_bugzilla("https://bugzilla.suse.com", bsc_list, creds["bugzilla.suse.com"])
    do_github(gh_list, creds["github.com"])
    do_gitlab(None, gl_list, creds["gitlab.com"])
    do_gitlab("https://gitlab.suse.de", gsd_list, creds["gitlab.suse.de"])
    do_redmine("https://progress.opensuse.org", poo_list, creds["progress.opensuse.org"])


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        sys.exit(1)
