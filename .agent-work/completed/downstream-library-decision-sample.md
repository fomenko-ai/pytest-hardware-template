# Downstream library decision sample

State: complete

## Result

Added a clearly identified architecture decision sample for projects created from this template.
It covers deliberate adoption of template updates before library publication and requires a
separate migration decision after a stable library API becomes available. The decision-record
guidance links to the sample and distinguishes samples from this repository's own decisions.

## Verification

- `git diff --check`: passed.
- `./scripts/ci.sh`: all hooks and unit and integration tests passed; the initial run reached the
  final clean-diff check and failed because the intended documentation changes were unstaged.
- Final `./scripts/ci.sh` run after staging the intended changes: passed.
