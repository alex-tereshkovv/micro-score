# Supply-Chain Gate v1

MicroScore treats dependency and build inputs as reviewable engineering state.
The gate has two layers.

## Required CI audit

The main test job installs `pip-audit` and audits the installed Python
environment with:

```text
python -m pip freeze --exclude-editable > /tmp/microscore-installed.txt
python -m pip_audit --requirement /tmp/microscore-installed.txt --strict
```

The first command captures exact versions from the installed CI environment
while excluding the editable MicroScore package itself. Known vulnerabilities
make the audit fail. `--strict` also fails when an installed dependency cannot
be audited.

The release requirements install the `app` and `report` extras only. Jupyter is
kept as an explicit notebook-development extra because it is not used by the
API, tests, report builders, or deployed container. This reduces the release
dependency surface without removing notebook support from the project.

This is a current vulnerability-database check, not a proof that dependencies
are defect-free. Results can change when advisories are published, so the gate
runs on every push and pull request.

## Automated update discovery

`.github/dependabot.yml` checks three ecosystems every week:

- Python packages;
- Docker base images;
- GitHub Actions.

Dependabot proposals still require the complete project CI gate. Automatic
discovery does not mean automatic acceptance.

## Remaining production controls

Before a real deployment, add reviewed lockfiles or constraints with hashes,
artifact provenance and signing, a retained SBOM, secret scanning, protected
branches, and an explicit vulnerability-response owner and service level.
Container images should be pinned to reviewed digests in the deployment
environment. These controls are intentionally not claimed by Supply-Chain Gate
v1.
