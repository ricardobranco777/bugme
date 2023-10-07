"""
Guess service
"""

from functools import cache
from typing import Any

import requests
from requests.exceptions import RequestException

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
        "github.com": MyGithub,
        "bitbucket.org": MyBitbucket,
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

    if "gogs" in server:
        return MyGogs

    suffixes: dict[str, Any] = {
        "launchpad.net": MyLaunchpad,
    }
    for suffix, cls in suffixes.items():
        if server.endswith(suffix):
            return cls

    endpoints: dict[Any, str] = {
        MyJira: "rest/api/2/serverInfo",
        MyAllura: "rest/",
        MyRedmine: "issues.json",
        MyGitea: "swagger.v1.json",
        # MyGitea: "api/v1/version",
        MyPagure: "api/0/version",
    }

    for cls, endpoint in endpoints.items():
        api_endpoint = f"https://{server}/{endpoint}"
        try:
            response = requests.head(api_endpoint, allow_redirects=True, timeout=5)
            response.raise_for_status()
            if response.status_code == 200:
                return cls
        except RequestException:
            pass

    return None
