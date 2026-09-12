# README references

Result: appended References to README.md with the user-provided Habr URL.
At the user's request, translated the article title into English and added (RU).
Moved the virtual stand paragraph and screenshot (former lines 547–551) after
line 516 at the user's request.
Reapplied the move after verifying it had been reverted; preserved the user's
updated English article title punctuation.
Linked the runner's Allure and ReportPortal mentions to their respective
Test Runner integration instructions; verified both target headings exist.
Added Reporting examples with Test Runner, Allure, and ReportPortal subheadings.
Formatted screenshot captions with sub tags and restored the UI caption beneath
its matching screenshot. Removed paragraph gaps for all eight captions by
joining each image and caption with an explicit HTML line break.
Centered all eight image-caption pairs in HTML paragraphs and added a line
break after each pair to separate it from the following content.
Verification: git diff --check passed. ./scripts/ci.sh could not run because
the sandbox prevents uv from writing to /home/duryspa/.cache/uv.
The request to stage README and run CI outside the sandbox was declined.
README remains unstaged. Full CI verification remains outstanding.
