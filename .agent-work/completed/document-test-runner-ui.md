# Document test runner UI

## Result

Documented both service interfaces in the helper README:

- moved the main UI screenshot to `docs/images/ui-overview.png` and embedded it near the README
  introduction;
- renamed the login screenshot to `docs/images/authentication-login.png` and embedded it in the
  authentication section;
- embedded the main UI screenshot in the repository README to make the optional service more
  discoverable;
- added descriptive alternative text for both screenshots.

## Verification

- Both screenshots are valid 2430 x 1413 PNG files and their relative README links resolve to them.
- `git diff --check` passed.
- All checks inside `./scripts/ci.sh` passed; the script's final `git diff --exit-code` reported the
  intended unstaged README change.
