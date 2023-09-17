"""
Create creds.json
"""

import json
import os

CREDS = {
    "bugzilla.suse.com": {
        "api_key": os.getenv("BUGZILLA_API_KEY"),
        "user": os.getenv("BUGZILLA_USER"),
    },
    "github.com": {"login_or_token": os.getenv("BUGME_GITHUB_TOKEN")},
    "gitlab.com": {"private_token": os.getenv("GITLAB_API_KEY")},
    "jira.suse.com": {
        "cookies": {
            "JIRASESSIONID": os.getenv("JIRA_SESSION_ID"),
            "atlassian.xsrf.token": os.getenv("JIRA_TOKEN"),
        }
    },
    "progress.opensuse.org": {
        "key": os.getenv("REDMINE_API_KEY"),
        "username": os.getenv("REDMINE_USER"),
    },
}


if __name__ == "__main__":
    os.umask(0o077)
    with open("creds.json", "w", encoding="utf-8") as file:
        file.write(json.dumps(CREDS))
