"""
Services
"""

import logging
import os
import re
from concurrent.futures import ThreadPoolExecutor
from functools import cache
from urllib.parse import urlparse, parse_qs
from typing import Any

from datetime import datetime
from pytz import utc

from atlassian import Jira  # type: ignore
from atlassian.errors import ApiError  # type: ignore
from bugzilla import Bugzilla  # type: ignore
from bugzilla.exceptions import BugzillaError  # type: ignore
from github import Github, GithubException  # , Auth
from gitlab import Gitlab
from gitlab.exceptions import GitlabError
from redminelib import Redmine  # type: ignore
from redminelib.exceptions import BaseRedmineError, ResourceNotFoundError  # type: ignore

import requests
from requests.exceptions import RequestException
from requests_toolbelt.utils import dump  # type: ignore

from utils import utc_date


TAG_REGEX = "|".join(
    [
        r"(?:bnc|bsc|boo|poo)#[0-9]+",
        r"(?:gh|gl|gsd|coo|soo)#[^#]+#[0-9]+",
        r"jsc#[A-Z]+-[0-9]+",
    ]
)

TAG_TO_HOST = {
    "bnc": "bugzilla.suse.com",
    "bsc": "bugzilla.suse.com",
    "boo": "bugzilla.suse.com",
    "gh": "github.com",
    "gl": "gitlab.com",
    "gsd": "gitlab.suse.de",
    "jsc": "jira.suse.com",
    "poo": "progress.opensuse.org",
    "coo": "code.opensuse.org",
    "soo": "src.opensuse.org",
}


def debugme(got, *args, **kwargs):  # pylint: disable=unused-argument
    """
    Print requests response
    """
    got.hook_called = True
    print(dump.dump_all(got).decode("utf-8"))
    return got


class Issue:  # pylint: disable=too-few-public-methods
    """
    Issue class
    """

    def __init__(self, **kwargs):
        for attr, value in kwargs.items():
            setattr(self, attr, value)

    def __repr__(self):
        attrs = ", ".join(f"{attr}={getattr(self, attr)!r}" for attr in vars(self))
        return f"{self.__class__.__name__}({attrs})"

    def sort_key(self) -> tuple[str, int]:
        """
        Key for numeric sort of URL's ending with digits
        """
        base, issue_id, _ = re.split(
            r"([0-9]+)$", self.url, maxsplit=1  # pylint: disable=no-member
        )
        return base, int(issue_id)

    # Allow access this object as a dictionary

    def __getitem__(self, item: str) -> Any:
        try:
            return getattr(self, item)
        except AttributeError as exc:
            raise KeyError(exc) from exc

    def __setitem__(self, item: str, value: Any) -> None:
        setattr(self, item, value)


def get_urltag(string: str) -> dict[str, str] | None:
    """
    Get tag or URL from string
    """
    if "#" not in string:
        # URL
        string = string if string.startswith("https://") else f"https://{string}"
        url = urlparse(string)
        hostname = url.hostname.removeprefix("www.") if url.hostname is not None else ""
        repo: str = ""
        if hostname.startswith("bugzilla"):
            issue_id = parse_qs(url.query)["id"][0]
        elif not url.path.startswith("/issues/") and "/issue" in url.path:
            repo = os.path.dirname(
                os.path.dirname(url.path.replace("/-/", "/"))
            ).lstrip("/")
            issue_id = os.path.basename(url.path)
        else:
            issue_id = os.path.basename(url.path)
        return {
            "issue_id": issue_id,
            "host": hostname,
            "repo": repo,
        }
    # Tag
    if not re.fullmatch(TAG_REGEX, string):
        logging.warning("Skipping unsupported %s", string)
        return None
    try:
        code, repo, issue = string.split("#", 2)
    except ValueError:
        code, issue = string.split("#", 1)
        repo = ""
    return {
        "issue_id": issue,
        "host": TAG_TO_HOST[code],
        "repo": repo,
    }


class Service:
    """
    Service class to abstract methods
    """

    def __init__(self, url: str):
        url = url.rstrip("/")
        self.url = url if url.startswith("https://") else f"https://{url}"
        self.tag = "".join([s[0] for s in str(urlparse(self.url).hostname).split(".")])

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        if exc_type is not None:
            logging.error(
                "%s: %s: %s: %s",
                self.__class__.__name__,
                exc_type,
                exc_value,
                traceback,
            )

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}(url='{self.url}')"

    def _not_found(self, url: str, tag: str) -> Issue:
        now = datetime.now(tz=utc)
        return Issue(
            tag=tag,
            url=url,
            assignee="none",
            creator="none",
            created=now,
            updated=now,
            status="ERROR",
            title="NOT FOUND",
            raw={},
        )

    def get_issue(self, issue_id: str = "", **kwargs) -> Issue | None:
        """
        This method must be overriden if get_issues() isn't overriden
        """
        raise NotImplementedError(f"{self.__class__.__name__}: get_issue()")

    def get_issues(self, issues: list[dict]) -> list[Issue | None]:
        """
        Multithreaded get_issues()
        """
        with ThreadPoolExecutor(max_workers=min(10, len(issues))) as executor:
            return list(executor.map(lambda it: self.get_issue(**it), issues))


class MyBugzilla(Service):
    """
    Bugzilla
    """

    def __init__(self, url: str, creds: dict):
        super().__init__(url)
        options = {
            "force_rest": True,
            "sslverify": os.environ.get("REQUESTS_CA_BUNDLE", True),
        }
        options |= creds
        try:
            self.client = Bugzilla(self.url, **options)
        except (BugzillaError, RequestException) as exc:
            logging.error("Bugzilla: %s: %s", self.url, exc)
        if os.getenv("DEBUG"):
            self.client._session._session.hooks["response"].append(debugme)

    def __del__(self):
        try:
            self.client.disconnect()
        except (AttributeError, BugzillaError):
            pass

    def __exit__(self, exc_type, exc_value, traceback):
        self.__del__()
        super().__exit__(exc_type, exc_value, traceback)

    def get_issue(self, issue_id: str = "", **kwargs) -> Issue | None:
        """
        Get Bugzilla issue
        """
        try:
            return self._to_issue(self.client.getbug(issue_id))
        except IndexError:
            return self._not_found(
                url=f"{self.url}/show_bug.cgi?id={issue_id}",
                tag=f"{self.tag}#{issue_id}",
            )
        except (AttributeError, BugzillaError, RequestException) as exc:
            logging.error("Bugzilla: %s: get_issue(%s): %s", self.url, issue_id, exc)
        return None

    def get_issues(self, issues: list[dict]) -> list[Issue | None]:
        """
        Get Bugzilla issues
        """
        try:
            found = [
                self._to_issue(info)
                for info in self.client.getbugs([issue["issue_id"] for issue in issues])
            ]
        except (AttributeError, BugzillaError, RequestException) as exc:
            logging.error("Bugzilla: %s: get_issues(): %s", self.url, exc)
            return []
        # Bugzilla silently fails on not found issues
        found_ids = {str(issue.raw["id"]) for issue in found}
        not_found = [
            self._not_found(
                url=f"{self.url}/show_bug.cgi?id={issue['issue_id']}",
                tag=f"{self.tag}#{issue['issue_id']}",
            )
            for issue in issues
            if issue["issue_id"] not in found_ids
        ]
        return found + not_found  # type: ignore

    def _to_issue(self, info: Any) -> Issue:
        return Issue(
            tag=f"{self.tag}#{info.id}",
            url=f"{self.url}/show_bug.cgi?id={info.id}",
            assignee=info.assigned_to or "none",
            creator=info.creator,
            created=utc_date(info.creation_time),
            updated=utc_date(info.last_change_time),
            closed=utc_date(info.last_change_time if not info.is_open else None),
            status=info.status.upper().replace(" ", "_"),
            title=info.summary,
            raw=info.get_raw_data(),
        )


class MyGithub(Service):
    """
    Github
    """

    def __init__(self, url: str, creds: dict):
        super().__init__(url)
        # NOTE: Uncomment when latest PyGithub is published on Tumbleweed
        # auth = Auth.Token(**creds)
        # self.client = Github(auth=auth)
        self.tag = "gh"
        self.client = Github(**creds)
        if os.getenv("DEBUG"):
            logging.getLogger("github").setLevel(logging.DEBUG)

    def __del__(self):
        try:
            self.client.close()
        except (AttributeError, GithubException):
            pass

    def get_issue(self, issue_id: str = "", **kwargs) -> Issue | None:
        """
        Get Github issue
        """
        repo = kwargs.pop("repo")
        try:
            info = self.client.get_repo(repo, lazy=True).get_issue(int(issue_id))
        except (GithubException, RequestException) as exc:
            if getattr(exc, "status", None) == 404:
                return self._not_found(
                    url=f"{self.url}/{repo}/issues/{issue_id}",
                    tag=f"{self.tag}#{repo}#{issue_id}",
                )
            logging.error("Github: get_issue(%s, %s): %s", repo, issue_id, exc)
            return None
        return self._to_issue(info, repo)

    def _to_issue(self, info: Any, repo: str) -> Issue:
        return Issue(
            tag=f"{self.tag}#{repo}#{info.number}",
            url=f"{self.url}/{repo}/issues/{info.number}",
            assignee=info.assignee.login if info.assignee else "none",
            creator=info.user.login,
            created=utc_date(info.created_at),
            updated=utc_date(info.updated_at),
            closed=utc_date(info.closed_at),
            status=info.state.upper().replace(" ", "_"),
            title=info.title,
            raw=info.raw_data,
        )


class MyGitlab(Service):
    """
    Gitlab
    """

    def __init__(self, url: str, creds: dict):
        super().__init__(url)
        options: dict[str, Any] = {
            "ssl_verify": os.environ.get("REQUESTS_CA_BUNDLE", True),
        }
        options |= creds
        hostname = str(urlparse(self.url).hostname)
        self.tag = "gl" if hostname == "gitlab.com" else self.tag
        self.client = Gitlab(url=self.url, **options)
        if os.getenv("DEBUG"):
            self.client.session.hooks["response"].append(debugme)

    def __del__(self):
        try:
            self.client.__exit__(None, None, None)
        except (AttributeError, GitlabError):
            pass

    def __exit__(self, exc_type, exc_value, traceback):
        self.__del__()
        super().__exit__(exc_type, exc_value, traceback)

    def get_issue(self, issue_id: str = "", **kwargs) -> Issue | None:
        """
        Get Gitlab issue
        """
        repo = kwargs.pop("repo")
        try:
            info = self.client.projects.get(repo, lazy=True).issues.get(issue_id)
        except (GitlabError, RequestException) as exc:
            if getattr(exc, "response_code", None) == 404:
                return self._not_found(
                    url=f"{self.url}/{repo}/-/issues/{issue_id}",
                    tag=f"{self.tag}#{repo}#{issue_id}",
                )
            logging.error(
                "Gitlab: %s: get_issue(%s, %s): %s", self.url, repo, issue_id, exc
            )
            return None
        return self._to_issue(info, repo)

    def _to_issue(self, info: Any, repo: str) -> Issue:
        return Issue(
            tag=f"{self.tag}#{repo}#{info.iid}",
            url=f"{self.url}/{repo}/-/issues/{info.iid}",
            assignee=info.assignee["name"] if info.assignee else "none",
            creator=info.author["name"],
            created=utc_date(info.created_at),
            updated=utc_date(info.updated_at),
            closed=utc_date(info.closed_at),
            status=info.state.upper().replace(" ", "_"),
            title=info.title,
            raw=info.asdict(),
        )


class MyRedmine(Service):
    """
    Redmine
    """

    def __init__(self, url: str, creds: dict):
        super().__init__(url)
        options = {
            "raise_attr_exception": False,
        }
        options |= creds
        self.client = Redmine(url=self.url, **options)
        if os.getenv("DEBUG"):
            self.client.engine.session.hooks["response"].append(debugme)
        # Avoid API key leak: https://github.com/maxtepkeev/python-redmine/issues/330
        key = self.client.engine.requests["params"].get("key")
        # Workaround inspired from https://github.com/maxtepkeev/python-redmine/pull/328
        if key is not None:
            self.client.engine.requests["headers"]["X-Redmine-API-Key"] = key
            del self.client.engine.requests["params"]["key"]

    def get_issue(self, issue_id: str = "", **kwargs) -> Issue | None:
        """
        Get Redmine ticket
        """
        try:
            info = self.client.issue.get(issue_id)
        except ResourceNotFoundError:
            return self._not_found(
                url=f"{self.url}/issues/{issue_id}", tag=f"{self.tag}#{issue_id}"
            )
        except (BaseRedmineError, RequestException) as exc:
            logging.error("Redmine: %s: get_issue(%s): %s", self.url, issue_id, exc)
            return None
        return self._to_issue(info)

    def _to_issue(self, info: Any) -> Issue:
        return Issue(
            tag=f"{self.tag}#{info.id}",
            url=f"{self.url}/issues/{info.id}",
            assignee=info.assigned_to.name if info.assigned_to else "none",
            creator=info.author.name,
            created=utc_date(info.created_on),
            updated=utc_date(info.updated_on),
            closed=utc_date(info.closed_on),
            status=info.status.name.upper().replace(" ", "_"),
            title=info.subject,
            raw=info.raw(),
        )


class MyJira(Service):
    """
    Jira
    """

    def __init__(self, url: str, creds: dict):
        super().__init__(url)
        self.client = Jira(url=self.url, **creds)
        if os.getenv("DEBUG"):
            self.client.session.hooks["response"].append(debugme)

    def get_issue(self, issue_id: str = "", **kwargs) -> Issue | None:
        """
        Get Jira ticket
        """
        try:
            info = self.client.issue(issue_id)
        except (ApiError, RequestException) as exc:
            try:
                if getattr(exc.response, "status_code") == 404:
                    return self._not_found(
                        url=f"{self.url}/browse/{issue_id}",
                        tag=f"{self.tag}#{issue_id}",
                    )
            except AttributeError:
                pass
            logging.error("Jira: %s: get_issue(%s): %s", self.url, issue_id, exc)
            return None
        return self._to_issue(info)

    def _to_issue(self, info: Any) -> Issue:
        return Issue(
            tag=f"{self.tag}#{info['key']}",
            url=f"{self.url}/browse/{info['key']}",
            assignee=info["fields"]["assignee"]["name"]
            if info["fields"]["assignee"]
            else "none",
            creator=info["fields"]["creator"]["name"],
            created=utc_date(info["fields"]["created"]),
            updated=utc_date(info["fields"]["updated"]),
            closed=utc_date(info["fields"]["resolutiondate"]),
            status=info["fields"]["status"]["name"].upper().replace(" ", "_"),
            title=info["fields"]["summary"],
            raw=info,
        )


class Generic(Service):
    """
    Generic class for services using python requests
    """

    def __init__(self, url: str, token: str | None):
        super().__init__(url)
        self.api_url = "OVERRIDE"
        self.session = requests.Session()
        if token is not None:
            self.session.headers["Authorization"] = f"token {token}"
        self.session.headers["Accept"] = "application/json"
        if os.getenv("DEBUG"):
            self.session.hooks["response"].append(debugme)
        self.timeout = 10

    def __del__(self):
        self.session.close()

    def __exit__(self, exc_type, exc_value, traceback):
        self.__del__()
        super().__exit__(exc_type, exc_value, traceback)

    def get_issue(self, issue_id: str = "", **kwargs) -> Issue | None:
        """
        Get Git issue
        """
        repo = kwargs.pop("repo")
        try:
            got = self.session.get(
                self.api_url.format(repo=repo, issue=issue_id), timeout=self.timeout
            )
            got.raise_for_status()
            info = got.json()
        except RequestException as exc:
            try:
                if getattr(exc.response, "status_code") == 404:
                    return self._not_found(
                        url=self.issue_url.format(repo=repo, issue=issue_id),
                        tag=f"{self.tag}#{repo}#{issue_id}",
                    )
            except AttributeError:
                pass
            logging.error(
                "%s: get_issue(%s, %s): %s",
                self.__class__.__name__,
                repo,
                issue_id,
                exc,
            )
            return None
        return self._to_issue(info, repo)

    def _to_issue(self, info: Any, repo: str) -> Issue:
        raise NotImplementedError(f"{self.__class__.__name__}: to_issue()")


class MyGitea(Generic):
    """
    Gitea
    """

    def __init__(self, url: str, creds: dict, **_):
        super().__init__(url, token=creds.get("token"))
        self.api_url = f"{self.url}/api/v1/repos/{{repo}}/issues/{{issue}}"
        self.issue_url = f"{self.url}/{{repo}}/issues/{{issue}}"

    def _to_issue(self, info: Any, repo: str) -> Issue:
        return Issue(
            tag=f'{self.tag}#{repo}#{info["number"]}',
            url=f'{self.url}/{repo}/issues/{info["number"]}',
            assignee=info["assignee"]["name"] if info["assignee"] else "none",
            creator=info["user"]["login"],
            created=utc_date(info["created_at"]),
            updated=utc_date(info["updated_at"]),
            closed=utc_date(info["closed_at"]),
            status=info["state"].upper().replace(" ", "_"),
            title=info["title"],
            raw=info,
        )


class MyPagure(Generic):
    """
    Pagure
    """

    def __init__(self, url: str, creds: dict, **_):
        super().__init__(url, token=creds.get("token"))
        self.api_url = f"{self.url}/api/0/{{repo}}/issue/{{issue}}"
        self.issue_url = f"{self.url}/{{repo}}/issue/{{issue}}"

    def _to_issue(self, info: Any, repo: str) -> Issue:
        return Issue(
            tag=f'{self.tag}#{repo}#{info["id"]}',
            url=f'{self.url}/{repo}/issue/{info["id"]}',
            assignee=info["assignee"]["name"] if info["assignee"] else "none",
            creator=info["user"]["name"],
            created=utc_date(info["date_created"]),
            updated=utc_date(info["last_updated"]),
            closed=utc_date(info["closed_at"]),
            status=info["status"].upper().replace(" ", "_"),
            title=info["title"],
            raw=info,
        )


class MyGogs(Generic):
    """
    Gogs
    """

    def __init__(self, url: str, creds: dict, **_):
        super().__init__(url, token=creds.get("token"))
        self.api_url = f"{self.url}/api/v1/repos/{{repo}}/issues/{{issue}}"
        self.issue_url = f"{self.url}/{{repo}}/issues/{{issue}}"

    def _to_issue(self, info: Any, repo: str) -> Issue:
        return Issue(
            tag=f'{self.tag}#{repo}#{info["number"]}',
            url=f'{self.url}/{repo}/issues/{info["number"]}',
            assignee=info["assignee"]["username"] if info["assignee"] else "none",
            creator=info["user"]["username"],
            created=utc_date(info["created_at"]),
            updated=utc_date(info["updated_at"]),
            closed=utc_date(
                info["milestone"]["closed_at"] if info["milestone"] else None
            ),
            status=info["state"].upper().replace(" ", "_"),
            title=info["title"],
            raw=info,
        )


@cache  # pylint: disable=method-cache-max-size-none
def guess_service(server: str) -> Any:
    """
    Guess service
    """
    if server == "github.com":
        return MyGithub
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

    endpoints: dict[Any, str] = {
        MyJira: "rest/api/",
        MyRedmine: "issues.json",
        MyGitea: "swagger.v1.json",
        MyPagure: "api/0/version",
    }

    for cls, endpoint in endpoints.items():
        api_endpoint = f"https://{server}/{endpoint}"
        try:
            response = requests.head(api_endpoint, allow_redirects=True, timeout=7)
            response.raise_for_status()
            if response.status_code == 200:
                return cls
        except RequestException:
            pass

    return None
