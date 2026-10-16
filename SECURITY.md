# Security Policy

## Reporting a vulnerability

Please report vulnerabilities privately through GitHub Security Advisories:
open the repository's Security tab and click "Report a vulnerability". This
opens a private advisory thread visible only to you and the maintainer.

Do not open a public issue for security-sensitive reports.

## Scope

- The Python programs in this repository (all files ending in .py).
- The repository and its release process.

Out of scope: upstream Python standard library issues. Report those to
https://www.python.org/dev/security/ instead.

## Notes for reviewers

These programs are terminal simulations. They make no network connections,
read no files other than their own trace output, take no credentials, and
have no third-party dependencies. Their only writes are the trace log files
they are explicitly asked to produce.
