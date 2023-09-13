#!BuildTag: bugme
#!UseOBSRepositories
#FROM	registry.opensuse.org/opensuse/bci/python:3.11
FROM	opensuse/bci/python:3.11

#RUN	zypper addrepo https://download.opensuse.org/repositories/SUSE:/CA/openSUSE_Tumbleweed/SUSE:CA.repo && \
#	zypper --gpg-auto-import-keys -n install ca-certificates-suse
COPY	SUSE_Trust_Root.crt /usr/share/pki/trust/anchors/
RUN	update-ca-certificates

RUN	zypper -n install \
		python3-python-dateutil \
		python3-pytz \
		python3-Jinja2 \
		python3-bugzilla \
		python3-PyGithub \
		python3-python-gitlab \
		python3-python-redmine && \
	zypper clean -a

COPY	*.py /

ENV	REQUESTS_CA_BUNDLE=/etc/ssl/ca-bundle.pem

WORKDIR	/bugme

ENTRYPOINT ["/usr/bin/python3", "/bugme.py"]
