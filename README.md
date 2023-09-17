![Build Status](https://github.com/ricardobranco777/bugme/actions/workflows/ci.yml/badge.svg)

# bugme

Show bug and issue status for Bugzilla, Github, Gitlab, Jira & Redmine

Docker image available at `ghcr.io/ricardobranco777/bugme:latest`

List of soft-failures for [os-autoinst-distri-opensuse](https://github.com/os-autoinst/os-autoinst-distri-opensuse) available at:

https://ricardobranco777.github.io/bugme/

## Usage

```
usage: bugme.py [-h] [-c CREDS] [-f FORMAT] [-l {debug,info,warning,error,critical}] [-o {text,json}] [-t TIME] [--version] [url ...]

positional arguments:
  url

options:
  -h, --help            show this help message and exit
  -c CREDS, --creds CREDS
                        path to credentials file (default: ~/creds.json)
  -f FORMAT, --format FORMAT
                        output fields (default: tag,status,updated,title)
  -l {debug,info,warning,error,critical}, --log {debug,info,warning,error,critical}
                        log level (default: warning)
  -o {text,html}, --output {text,html}
                        output type (default: text)
  -t TIME, --time TIME  strftime format (default: timeago)
  --version             show program's version number and exit
```

## Example

Copy [creds-example.json](creds-example.json) to `~/creds.json` and run:

```
$ podman run --rm -v ~/creds.json:/root/creds.json:ro bugme bsc#1213811 gh#containers/podman#19529 poo#133910 gl#gitlab-org/gitlab#424503 gsd#qac/container-release-bot#7 ghcr.io/ricardobranco777/bugme
TAG                                       STATUS           UPDATED          TITLE
bsc#1213811                               NEW              2 days ago       podman network unreachable after starting docker
gh#containers/podman#19529                CLOSED           1 month ago      Unexpected error with --volumes-from
poo#133910                                RESOLVED         1 month ago      We need a suite of tests to check volume operations in container runtimes
gl#gitlab-org/gitlab#424503               OPENED           5 days ago       Prepare UI/UX when monetisation transition period ends (cut-off)
gsd#qac/container-release-bot#7           OPENED           1 year ago       Explore new schedule options
jsc#SCL-8                                 IN PROGRESS      1 year ago       Documentation
```

To scan a repository:

```
$ podman run --rm -v ~/creds.json:/root/creds.json:ro -v ~/suse/os-autoinst-distri-opensuse:/bugme:ro
```

## Supported tags

- bsc#: SUSE's Bugzilla
- gh#: Github
- gl#: Gitlab
- gsd#: SUSE's Gitlab
- jsc#: SUSE's Jira
- poo#: openSUSE's Redmine

## Requirements

- Docker or Podman to run the Docker image.
- Python 3.11+ and [requirements](requirements-dev.txt) to run stand-alone.
