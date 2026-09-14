# Refine the runtime/reporting implementation plan

Owner: /root
Status: complete

Updated the saved plan to place reporting policy in existing tests/conftest.py,
without a root conftest.py. Removed old-image/runner compatibility requirements:
update both together, rebuild images, and provide no legacy detection or fallback.
Default report paths and existing artifacts remain unchanged.

Verification: git diff --check and scripts/ci.sh passed. No implementation files
were changed; earlier staged work was preserved.
