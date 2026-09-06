# Optional Allure documentation

Owner: Codex
Status: complete

Scope: documentation only, README and this work record. No runtime or dependency changes.
Initial Git status was clean; no active task records existed.

Added recommendations for optional collection, unique artifacts directories, local viewing,
and external publication. Explicitly distinguish downstream integration from existing features.

Verification: git diff --check and the first ./scripts/ci.sh run passed. On the final CI run,
all hooks and non-hardware tests passed, but the final git diff check failed because an unrelated
unstaged change appeared in helpers/test-runner-service/docs/images/html-report-example.png.
That image was not edited or staged by this task. CI required access outside the sandbox to tool
caches. Documentation examples were reviewed against official Allure docs; Allure itself was not
installed or executed. No hardware tests were run.
