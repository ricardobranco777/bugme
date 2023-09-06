![Build Status](https://github.com/ricardobranco777/bugme/actions/workflows/ci.yml/badge.svg)

# bugme

Show bug and issue statuses

## Example usage

```
$ bugme.py bsc#1213811 gh#containers/podman#19529
bsc#1213811 NEW     Tue Sep 05 16:21:37 CEST 2023	podman network unreachable after starting docker
gh#19529	closed	Tue Aug 08 10:56:56 CEST 2023	Unexpected error with --volumes-from
```

## Requirements

- Tested on Python 3.8+
- [requirements](requirements-dev.txt)

## TODO

- Redmine
