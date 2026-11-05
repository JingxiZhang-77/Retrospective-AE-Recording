# Repository release checklist

## Ownership and permission

- [ ] Organizational permission to publish is documented.
- [ ] Any sponsor/client permissions and acknowledgements are resolved.
- [ ] Copyright ownership and the intended software license are approved.
- [ ] Replace the rights-reserved notice only with an approved license; do not
      describe this repository as open source while rights are reserved.
- [ ] Confirm the author and affiliation in `CITATION.cff`.

## Privacy and content

- [ ] No real participant, investigator, sponsor, study, site, or private path is
      present in public examples, logs, reports, XML, PDF metadata, or archives.
- [ ] No restricted source program, licensed terminology list, credential, or
      production configuration is included.
- [ ] Inspect the prepared release ZIP rather than uploading an entire working
      directory manually. Git ignore rules do not protect manual web uploads.
- [ ] Keep real run reports in a controlled location; do not commit them.
- [ ] Run `python scripts/check_repository.py` and review its limits.

## Technical release

- [ ] Run the full regression suite with Excel and PDF dependencies installed.
- [ ] Run `python scripts/run_public_reference_simulation.py` and review the
      initial/resolved demonstration reports.
- [ ] Review the actual hosted CI run after upload; local tests do not prove CI ran.
- [ ] Approve/pin dependencies and workflow actions under organizational policy.
- [ ] Confirm version consistency across package metadata, source, and citation.
- [ ] Build the source release with `python scripts/package_release.py` and retain
      the SHA-256 printed by that command.
- [ ] Confirm that the designated remote repository contains the reviewed source
      version, that its address matches the paper and citation, and that the
      intended public view is correct before sharing the paper link.
- [ ] Tag the reviewed version. A persistent archive/DOI can be added later.

The release script prepares local files only. It does not create a remote
repository, accept a license, publish data, or grant approval.

