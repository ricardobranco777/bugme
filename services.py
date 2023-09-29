"""
Services
"""

import logging
import os
import re
from concurrent.futures import ThreadPoolExecutor
from urllib.parse import urlparse, parse_qs
from typing import Any

from datetime import datetime
from pytz import utc

from atlassian import Jira  # type: ignore
from atlassian.errors import ApiError  # type: ignore
from bugzilla import Bugzilla  # type: ignore
from bugzilla.exceptions import BugzillaError  # type: ignore
from github import Github, GithubException
from gitlab import Gitlab
from gitlab.exceptions import GitlabError
from redminelib import Redmine  # type: ignore
from redminelib.exceptions import BaseRedmineError, ResourceNotFoundError  # type: ignore

import requests
from requests.exceptions import RequestException
from cachetools import cached

from utils import utc_date


CODE_TO_HOST = {
    "bgo": "bugzilla.gnome.org",
    "bmo": "bugzilla.mozilla.org",
    "brc": "bugzilla.redhat.com",
    "bnc": "bugzilla.suse.com",
    "bsc": "bugzilla.suse.com",
    "boo": "bugzilla.suse.com",
    "gh": "github.com",
    "gl": "gitlab.com",
    "gsd": "gitlab.suse.de",
    "jsc": "jira.suse.com",
    "poo": "progress.opensuse.org",
}


class Item:  # pylint: disable=too-few-public-methods
    """
    Item class
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
        base, item_id, _ = re.split(
            r"([0-9]+)$", self.url, maxsplit=1  # pylint: disable=no-member
        )
        return base, int(item_id)

    # Allow access this object as a dictionary

    def __getitem__(self, item: str) -> Any:
        try:
            return getattr(self, item)
        except AttributeError as exc:
            raise KeyError(exc) from exc

    def __setitem__(self, item: str, value: Any) -> None:
        setattr(self, item, value)


def get_item(string: str) -> dict[str, str] | None:
    """
    Get Item from string
    """
    if "#" not in string:
        # URL
        string = string if string.startswith("https://") else f"https://{string}"
        url = urlparse(string)
        hostname = url.hostname.removeprefix("www.") if url.hostname is not None else ""
        repo: str = ""
        if hostname.startswith("git"):
            repo = os.path.dirname(
                os.path.dirname(url.path.replace("/-/", "/"))
            ).lstrip("/")
            issue_id = os.path.basename(url.path)
        elif hostname.startswith("bugzilla"):
            issue_id = parse_qs(url.query)["id"][0]
        else:
            issue_id = os.path.basename(url.path)
        return {
            "item_id": issue_id,
            "host": hostname,
            "repo": repo,
        }
    # Tag
    try:
        code, repo, issue = string.split("#", 2)
    except ValueError:
        code, issue = string.split("#", 1)
        repo = ""
    try:
        return {
            "item_id": issue,
            "host": CODE_TO_HOST[code],
            "repo": repo,
        }
    except KeyError:
        logging.warning("Unsupported %s", string)
    return None


class Service:
    """
    Service class to abstract methods
    """

    def __init__(self, url: str):
        url = url.rstrip("/")
        self.url = url if url.startswith("https://") else f"https://{url}"
        self.tag = "".join([s[0] for s in str(urlparse(self.url).hostname).split(".")])

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}(url='{self.url}')"

    def _not_found(self, url: str, tag: str) -> Item:
        now = datetime.now(tz=utc)
        return Item(
            status="ERROR",
            title="NOT FOUND",
            created=now,
            updated=now,
            url=url,
            tag=tag,
            raw={},
        )

    def get_item(self, item_id: str = "", **kwargs) -> Item | None:
        """
        This method must be overriden if get_items() isn't overriden
        """
        raise NotImplementedError(f"{self.__class__.__name__}: get_item()")

    def get_items(self, items: list[dict]) -> list[Item | None]:
        """
        Multithreaded get_items()
        """
        with ThreadPoolExecutor(max_workers=min(10, len(items))) as executor:
            return list(executor.map(lambda it: self.get_item(**it), items))


class MyBugzilla(Service):
    """
    Bugzilla
    """

    def __init__(self, url: str, creds: dict, **kwargs):
        super().__init__(url)
        if "include_fields" in kwargs:
            self._include_fields = kwargs.pop("include_fields")
        kwargs |= creds
        try:
            self.client = Bugzilla(self.url, **kwargs)
        except (BugzillaError, RequestException) as exc:
            logging.error("Bugzilla: %s: %s", self.url, exc)

    def __del__(self):
        try:
            self.client.disconnect()
        except (AttributeError, BugzillaError):
            pass

    def get_item(self, item_id: str = "", **kwargs) -> Item | None:
        """
        Get Bugzilla item
        """
        try:
            return self._to_item(
                self.client.getbug(item_id, include_fields=self._include_fields)
            )
        except IndexError:
            return self._not_found(
                url=f"{self.url}/show_bug.cgi?id={item_id}",
                tag=f"{self.tag}#{item_id}",
            )
        except (AttributeError, BugzillaError, RequestException) as exc:
            logging.error("Bugzilla: %s: get_item(%s): %s", self.url, item_id, exc)
        return None

    def get_items(self, items: list[dict]) -> list[Item | None]:
        """
        Get Bugzilla items
        """
        try:
            found = [
                self._to_item(info)
                for info in self.client.getbugs(
                    [item["item_id"] for item in items],
                    include_fields=self._include_fields,
                )
            ]
        except (AttributeError, BugzillaError, RequestException) as exc:
            logging.error("Bugzilla: %s: get_items(): %s", self.url, exc)
            return []
        # Bugzilla silently fails on not found items
        found_ids = {str(item.raw["id"]) for item in found}
        not_found = [
            self._not_found(
                url=f"{self.url}/show_bug.cgi?id={item['item_id']}",
                tag=f"{self.tag}#{item['item_id']}",
            )
            for item in items
            if item["item_id"] not in found_ids
        ]
        return found + not_found  # type: ignore

    def _to_item(self, info: Any) -> Item:
        return Item(
            status=info.status.upper().replace(" ", "_"),
            title=info.summary,
            created=utc_date(info.creation_time),
            updated=utc_date(info.last_change_time),
            url=f"{self.url}/show_bug.cgi?id={info.id}",
            tag=f"{self.tag}#{info.id}",
            raw=info.get_raw_data(),
        )


class MyGithub(Service):
    """
    Github
    """

    def __init__(self, url: str, creds: dict, **kwargs):
        super().__init__(url)
        # Uncomment when latest PyGithub is published on Tumbleweed
        # auth = Auth.Token(**creds)
        # self.client = Github(auth=auth)
        kwargs |= creds
        self.client = Github(**kwargs)
        self.tag = "gh"

    def get_item(self, item_id: str = "", **kwargs) -> Item | None:
        """
        Get Github issue
        """
        repo = kwargs.pop("repo")
        try:
            info = self.client.get_repo(repo, lazy=True).get_issue(int(item_id))
        except (GithubException, RequestException) as exc:
            if getattr(exc, "status", None) == 404:
                return self._not_found(
                    url=f"{self.url}/{repo}/issues/{item_id}",
                    tag=f"{self.tag}#{repo}#{item_id}",
                )
            logging.error("Github: get_item(%s, %s): %s", repo, item_id, exc)
            return None
        return self._to_item(info, repo)

    def _to_item(self, info: Any, repo: str) -> Item:
        return Item(
            status=info.state.upper().replace(" ", "_"),
            title=info.title,
            created=utc_date(info.created_at),
            updated=utc_date(info.updated_at),
            url=f"{self.url}/{repo}/issues/{info.number}",
            tag=f"{self.tag}#{repo}#{info.number}",
            raw=info.raw_data,
        )


class MyGitlab(Service):
    """
    Gitlab
    """

    def __init__(self, url: str, creds: dict, **kwargs):
        super().__init__(url)
        kwargs |= creds
        self.client = Gitlab(url=self.url, **kwargs)
        hostname = str(urlparse(self.url).hostname)
        self.tag = "gl" if hostname == "gitlab.com" else self.tag

    def __del__(self):
        try:
            self.client.__exit__(None, None, None)
        except (AttributeError, GitlabError):
            pass

    def get_item(self, item_id: str = "", **kwargs) -> Item | None:
        """
        Get Gitlab issue
        """
        repo = kwargs.pop("repo")
        try:
            info = self.client.projects.get(repo, lazy=True).issues.get(item_id)
        except (GitlabError, RequestException) as exc:
            if getattr(exc, "response_code", None) == 404:
                return self._not_found(
                    url=f"{self.url}/{repo}/-/issues/{item_id}",
                    tag=f"{self.tag}#{repo}#{item_id}",
                )
            logging.error(
                "Gitlab: %s: get_item(%s, %s): %s", self.url, repo, item_id, exc
            )
            return None
        return self._to_item(info, repo)

    def _to_item(self, info: Any, repo: str) -> Item:
        return Item(
            status=info.state.upper().replace(" ", "_"),
            title=info.title,
            created=utc_date(info.created_at),
            updated=utc_date(info.updated_at),
            url=f"{self.url}/{repo}/-/issues/{info.iid}",
            tag=f"{self.tag}#{repo}#{info.iid}",
            raw=info.asdict(),
        )


class MyRedmine(Service):
    """
    Redmine
    """

    def __init__(self, url: str, creds: dict, **kwargs):
        super().__init__(url)
        kwargs |= creds
        self.client = Redmine(url=self.url, **kwargs)
        # Avoid API key leak: https://github.com/maxtepkeev/python-redmine/issues/330
        key = self.client.engine.requests["params"].get("key")
        # Workaround inspired from https://github.com/maxtepkeev/python-redmine/pull/328
        if key is not None:
            self.client.engine.requests["headers"]["X-Redmine-API-Key"] = key
            del self.client.engine.requests["params"]["key"]

    def get_item(self, item_id: str = "", **kwargs) -> Item | None:
        """
        Get Redmine ticket
        """
        try:
            info = self.client.issue.get(item_id)
        except ResourceNotFoundError:
            return self._not_found(
                url=f"{self.url}/issues/{item_id}", tag=f"{self.tag}#{item_id}"
            )
        except (BaseRedmineError, RequestException) as exc:
            logging.error("Redmine: %s: get_item(%s): %s", self.url, item_id, exc)
            return None
        return self._to_item(info)

    def _to_item(self, info: Any) -> Item:
        return Item(
            status=info.status.name.upper().replace(" ", "_"),
            title=info.subject,
            created=utc_date(info.created_on),
            updated=utc_date(info.updated_on),
            url=f"{self.url}/issues/{info.id}",
            tag=f"{self.tag}#{info.id}",
            raw=info.raw(),
        )


class MyJira(Service):
    """
    Jira
    """

    def __init__(self, url: str, creds: dict, **kwargs):
        super().__init__(url)
        kwargs |= creds
        self.client = Jira(url=self.url, **kwargs)

    def get_item(self, item_id: str = "", **kwargs) -> Item | None:
        """
        Get Jira ticket
        """
        try:
            info = self.client.issue(item_id)
        except (ApiError, RequestException) as exc:
            try:
                if getattr(exc.response, "status_code") == 404:
                    return self._not_found(
                        url=f"{self.url}/browse/{item_id}", tag=f"{self.tag}#{item_id}"
                    )
            except AttributeError:
                pass
            logging.error("Jira: %s: get_item(%s): %s", self.url, item_id, exc)
            return None
        return self._to_item(info)

    def _to_item(self, info: Any) -> Item:
        return Item(
            status=info["fields"]["status"]["name"].upper().replace(" ", "_"),
            title=info["fields"]["summary"],
            created=utc_date(info["fields"]["created"]),
            updated=utc_date(info["fields"]["updated"]),
            url=f"{self.url}/browse/{info['key']}",
            tag=f"{self.tag}#{info['key']}",
            raw=info,
        )


@cached(cache={})
def guess_service(server: str) -> Any:
    """
    Guess service
    """
    if server == "github.com":
        return MyGithub

    endpoints = {
        MyJira: "rest/api/",
        MyRedmine: "issues.json",
    }

    for cls, endpoint in endpoints.items():
        api_endpoint = f"https://{server}/{endpoint}"
        try:
            response = requests.head(api_endpoint, allow_redirects=True, timeout=7)
            if response.status_code == 200:
                return cls
        except RequestException:
            pass

    return None
