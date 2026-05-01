"""Version constants for Polymath AI substrate.

Bumping rules:
  * SCHEMA_VERSION: every breaking change to envelope, audit row, KG node, or
    reasoner tuple shape. Past JSONL is forward-compatible only when the
    minor version bumps; major bumps require a migration log entry under
    docs/DECISIONS.md.
  * __version__: package-level semver. Bumped on substantive behavior change.
"""

__version__ = "0.1.0"
SCHEMA_VERSION = "1.0.0"
