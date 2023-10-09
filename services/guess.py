"""
Guess service
"""

import os
from contextlib import closing
from functools import cache
from typing import Any

import requests
from requests.exceptions import RequestException

from . import debugme
from .bitbucket import MyBitbucket
from .bugzilla import MyBugzilla
from .gitea import MyGitea
from .github import MyGithub
from .gitlab import MyGitlab
from .gogs import MyGogs
from .jira import MyJira
from .launchpad import MyLaunchpad
from .pagure import MyPagure
from .redmine import MyRedmine
from .allura import MyAllura


@cache  # pylint: disable=method-cache-max-size-none
def guess_service(server: str) -> Any:
    """
    Guess service
    """
    servers: dict[str, Any] = {
        "code.opensuse.org": MyPagure,
        "progress.opensuse.org": MyRedmine,
        "src.opensuse.org": MyGitea,
    }
    for hostname, cls in servers.items():
        if hostname == server:
            return cls

    prefixes: dict[str, Any] = {
        "jira": MyJira,
        "gitlab": MyGitlab,
        "bugzilla": MyBugzilla,
    }
    for prefix, cls in prefixes.items():
        if server.startswith(prefix):
            return cls

    suffixes: dict[str, Any] = {
        "github.com": MyGithub,
        "launchpad.net": MyLaunchpad,
        "bitbucket.org": MyBitbucket,
    }
    for suffix, cls in suffixes.items():
        if server.endswith(suffix):
            return cls

    if "gogs" in server:
        return MyGogs

    return guess_service2(server)


def guess_service2(server: str) -> Any | None:
    """
    Guess service
    """
    # These should be tried in order
    endpoints = {
        "GET": (
            (MyGitlab, "api/v4/version", 401),
            (MyJira, "rest/api/2/serverInfo", 200),
            (MyBugzilla, "rest/version", 200),
            (MyGitea, "api/v1/version", 200),
            (MyPagure, "api/0/version", 200),
            (MyBitbucket, "2.0/user", 401),
        ),
        "HEAD": (
            (MyRedmine, "issues.json", 200),
            (MyAllura, "rest/", 200),
        ),
    }

    session = requests.Session()
    session.headers["Accept"] = "application/json"
    session.verify = os.environ.get("REQUESTS_CA_BUNDLE", True)
    if os.getenv("DEBUG"):
        session.hooks["response"].append(debugme)

    with closing(session):
        for method, want in endpoints.items():
            for cls, endpoint, status in want:
                url = f"https://{server}/{endpoint}"
                try:
                    response = session.request(method, url, timeout=5)
                    if response.status_code == status:
                        return cls
                except RequestException:
                    pass

    return None
