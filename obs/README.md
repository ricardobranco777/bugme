
To publish the image on `registry.opensuse.org` I had to use the [Open Build Service](https://openbuildservice.org/):

1. Add directives to [Dockerfile](../Dockerfile)
1. Branch https://build.opensuse.org/package/show/devel:BCI:Tumbleweed/python-3.11-image
1. Run `osc -A https://api.opensuse.org checkout home:rbranco`
1. `cd home:rbranco:branches:devel:BCI:Tumbleweed/bugme-image`
1. Add a [_service](_service) file with `osc add _service`
1. Run `osc ci`
1. Create a Github token with `repo` scope.
1. Create a OBS token with `osc token --create --operation workflow --scm-token XXX` with `XXX` being the Github token.
1. Create a webhook in Github with the above token and the URL https://build.opensuse.org/trigger/workflow?id=777 with the correct ID and the OBS token as secret
1. Create [.obs/workflows.yml](.obs/workflows.yml)

More information:
https://openbuildservice.org/help/manuals/obs-user-guide/cha.obs.scm_ci_workflow_integration
