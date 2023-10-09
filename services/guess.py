"""
Guess service
"""

import os
from concurrent.futures import ThreadPoolExecutor, as_completed
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

    def make_request(method: str, cls: Any, endpoint: str, status: int) -> Any | None:
        url = f"https://{server}/{endpoint}"
        try:
            response = session.request(method, url, timeout=5)
            if response.status_code == status:
                return cls
        except RequestException:
            pass
        return None

    max_workers = min(10, len(endpoints["GET"]) + len(endpoints["HEAD"]))
    with closing(session), ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = []
        for method, want in endpoints.items():
            for cls, endpoint, status in want:
                futures.append(
                    executor.submit(make_request, method, cls, endpoint, status)
                )

        for future in as_completed(futures):
            result = future.result()
            if result:
                return result

    return None
