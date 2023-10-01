"""
Module to get Git blame from Github's GraphQL API
"""

import logging
from functools import cache
from datetime import datetime

import requests
from requests.adapters import HTTPAdapter
from requests import RequestException

from utils import utc_date


_QUERY = """
query($owner: String!, $repositoryName: String!, $branchName: String!, $filePath: String!) {
  repositoryOwner(login: $owner) {
    repository(name: $repositoryName) {
      object(expression: $branchName) {
        ... on Commit {
          blame(path: $filePath) {
            ranges {
              startingLine
              endingLine
              commit {
                committedDate
                oid
                author {
                  name
                  email
                }
              }
            }
          }
        }
      }
    }
  }
}
"""


class GitBlame:
    """
    Class to get Git blame from Github's GraphQL API
    """

    def __init__(self, repo: str, branch: str, access_token: str) -> None:
        self.owner, self.repo = repo.split("/", 1)
        self.branch = branch
        self.api_url = "https://api.github.com/graphql"
        self.headers = {
            "Authorization": f"Bearer {access_token}",
        }
        self.session = requests.Session()
        self.session.mount(
            "https://", HTTPAdapter(pool_connections=50, pool_maxsize=50)
        )
        self.timeout = 30

    def close(self):
        """
        Close connections
        """
        self.session.close()

    @cache  # pylint: disable=method-cache-max-size-none
    def blame_file(self, file: str) -> dict | None:
        """
        Blame file
        """
        variables = {
            "owner": self.owner,
            "repositoryName": self.repo,
            "branchName": self.branch,
            "filePath": file,
        }
        try:
            response = self.session.post(
                self.api_url,
                timeout=self.timeout,
                headers=self.headers,
                json={"query": _QUERY, "variables": variables},
            )
            response.raise_for_status()
            data = response.json()["data"]
        except RequestException as exc:
            logging.error("%s: %s", file, exc)
            return None
        return data["repositoryOwner"]["repository"]["object"]["blame"]["ranges"]

    def blame_line(self, file: str, line: int) -> tuple[str, str, str, datetime]:
        """
        Blame line
        """
        blames = self.blame_file(file)
        if blames is None:
            raise KeyError("No blame")
        commit = None
        for blame in blames:
            if blame["startingLine"] <= line <= blame["endingLine"]:
                commit = blame["commit"]
        if commit is None:
            raise KeyError("No commit")
        author, email = commit["author"]["name"], commit["author"]["email"]
        # Sometimes these are swapped
        if "@" not in email and "@" in author:
            author, email = email, author
        return author, email, commit["oid"], utc_date(commit["committedDate"])
