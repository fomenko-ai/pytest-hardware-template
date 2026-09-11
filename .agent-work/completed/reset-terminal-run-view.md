# Reset terminal Test Runner view on reload

Moved persistent artifact and Allure history links next to Runner status. On initial page load, an
old terminal operation is presented as idle and its direct artifact/report links stay hidden, while
form values are restored. Active operations reconnect to their event stream.

Verification:

- focused Test Runner UI/API tests passed: 4 tests;
- the full non-hardware quality gate passed.
