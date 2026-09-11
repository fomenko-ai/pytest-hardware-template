# Update main README report images

State: complete.

Result:

- the main README shows the Allure report tree after the retained artifact index;
- the virtual-stand section uses the supplied successful virtual stand run screenshot;
- both referenced image files exist in the documented helper image directory.

Verification:

- `git diff --check` passed;
- `./scripts/ci.sh` passed (including Ruff, ShellCheck, ty, and unit/integration tests).
