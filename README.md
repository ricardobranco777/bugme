![Build Status](https://github.com/ricardobranco777/bugme/actions/workflows/ci.yml/badge.svg)

# bugme

Show bug and issue status for:

- [Apache Allura](https://allura.apache.org/)
- [Bitbucket](https://bitbucket.org/)
- [Bugzilla](https://www.bugzilla.org/)
- [Gitea](https://about.gitea.com/)
- [GitHub](https://github.com/)
- [GitLab](https://gitlab.com/)
- [Gogs](https://gogs.io/)
- [Jira](https://www.atlassian.com/software/jira)
- [Launchpad](https://launchpad.net/)
- [Pagure](https://pagure.io/)
- [Redmine](https://www.redmine.org/)

Docker image available at `ghcr.io/ricardobranco777/bugme:latest`

List of soft-failures for [os-autoinst-distri-opensuse](https://github.com/os-autoinst/os-autoinst-distri-opensuse) available at:

[https://ricardobranco777.github.io/bugme/](https://ricardobranco777.github.io/bugme/)

## Usage

```
usage: bugme.py [-h] [-c CREDS] [-f FIELDS]
                [-l {none,debug,info,warning,error,critical}]
                [-o {text,html,json}] [-r]
                [-s {tag,url,status,created,updated,assignee,creator}]
                [-S STATUS] [-t TIME_FORMAT] [--version]
                [url ...]

positional arguments:
  url

options:
  -h, --help            show this help message and exit
  -c CREDS, --creds CREDS
                        path to credentials file (default: ~/creds.json)
  -f FIELDS, --fields FIELDS
                        output fields (default: tag,status,updated,title)
  -l {none,debug,info,warning,error,critical}, --log {none,debug,info,warning,error,critical}
                        log level (default: warning)
  -o {text,html,json}, --output {text,html,json}
                        output type (default: text)
  -r, --reverse         reverse sort (default: False)
  -s {tag,url,status,created,updated,assignee,creator}, --sort {tag,url,status,created,updated,assignee,creator}
                        sort key (default: None)
  -S STATUS, --status STATUS
                        filter by status (may be specified multiple times) (default: None)
  -t TIME_FORMAT, --time TIME_FORMAT
  --version             show program's version number and exit

output fields for --fields: tag url status created updated title assignee creator
```

## Example

Copy [creds-example.json](creds-example.json) to `~/creds.json` and run:

```
$ podman run --rm -v ~/creds.json:/root/creds.json:ro ghcr.io/ricardobranco777/bugme -f url,status,updated,title bsc#1213811 gh#containers/podman#19529 poo#133910 gl#gitlab-org/gitlab#424503 gsd#qac/container-release-bot#7 jsc#SCL-8 soo#horse-race/Live-Broadcast-tv#1 coo#rbranco/test#1
URL                                                             STATUS       UPDATED        TITLE
https://bugzilla.suse.com/show_bug.cgi?id=1213811               NEW          19 days ago    podman network unreachable after starting docker
https://github.com/containers/podman/issues/19529               CLOSED       1 month ago    Unexpected error with --volumes-from
https://progress.opensuse.org/issues/133910                     RESOLVED     1 month ago    We need a suite of tests to check volume operations in container runtimes
https://gitlab.com/gitlab-org/gitlab/-/issues/424503            CLOSED       16 days ago    Prepare UI/UX when monetisation transition period ends (cut-off)
https://gitlab.suse.de/qac/container-release-bot/-/issues/7     OPENED       1 year ago     Explore new schedule options
https://jira.suse.com/browse/SCL-8                              IN_PROGRESS  1 year ago     Documentation
https://src.opensuse.org/horse-race/Live-Broadcast-tv/issues/1  ERROR        0 seconds ago  NOT FOUND
https://code.opensuse.org/rbranco/test/issue/1                  OPEN         1 day ago      test
```

To scan a repository:

```
$ podman run --rm -v ~/creds.json:/root/creds.json:ro -v ~/suse/os-autoinst-distri-opensuse:/bugme:ro ghcr.io/ricardobranco777/bugme
```

## Supported tags

- bnc# boo# bsc#: [openSUSE's Bugzilla](https://bugzilla.suse.com)
- gh#: [Github](https://github.com)
- gl#: [Gitlab](https://gitlab.com)
- gsd#: [SUSE's Gitlab](https://gitlab.suse.de)
- jsc#: [SUSE's Jira](https://jira.suse.com)
- poo#: [openSUSE's Redmine](https://progress.opensuse.org)
- soo#: [openSUSE's Gitea](https://src.opensuse.org)
- coo#: [openSUSE's Pagure](https://code.opensuse.org)
- lp#: [Ubuntu's Launchpad](https://launchpad.net)

## Requirements

- Docker or Podman to run the Docker image.
- Python 3.11+ and [requirements](requirements-dev.txt) to run stand-alone.
