"""
Create creds.json
"""

import json
import os

CREDS = {
    "bugzilla.suse.com": {
        "api_key": os.environ["BUGZILLA_API_KEY"],
        "user": os.environ["BUGZILLA_USER"],
    },
    "github.com": {"login_or_token": os.environ["BUGME_GITHUB_TOKEN"]},
    "gitlab.com": {"private_token": os.environ["GITLAB_API_KEY"]},
    "jira.suse.com": {
        "cookies": {
            "JIRASESSIONID": os.environ["JIRA_SESSION_ID"],
            "atlassian.xsrf.token": os.environ["JIRA_TOKEN"],
        }
    },
    "progress.opensuse.org": {
        "key": os.environ["REDMINE_API_KEY"],
        "username": os.environ["REDMINE_USER"],
    },
}


if __name__ == "__main__":
    os.umask(0o077)
    with open("creds.json", "w", encoding="utf-8") as file:
        file.write(json.dumps(CREDS))
