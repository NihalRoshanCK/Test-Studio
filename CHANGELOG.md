# Changelog

All notable changes to Test Studio. The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

## [Unreleased]

## [0.2.0] - 2026-11-17

### Security
- `login` steps check the password on the server and hand the browser a session: passwords are no longer typed in
  the page, so they no longer end up in Playwright traces or videos. Traces made before this release can contain the
  password typed at login; delete them if they may have been shared.

### Changed
- **Blocking email and SMS is now opt-in per site** (`test_studio_block_outgoing: 1` in site config). Before, installing
  Test Studio stopped all of a site's email and SMS. Test copies that relied on it must set the flag.
- The Desk apps-screen tile shows only to users who can open Test Studio.

### Added
- The **Test Studio User** role: write and run tests without being a System Manager.
- **Most runs at once** (Settings, default 3): runs outside the worker queue are refused beyond the limit. Runs stuck
  as Running for over an hour do not count.

### Fixed
- The MCP status check on the Settings page accepts only http and https addresses.
- `logs/test_studio_live.log` is rotated at 5 MB instead of growing forever.
- Tabs-only indentation where spaces were mixed in.

## [0.1.0] - 2026-11-17

### Added
- **Data-driven tests.** *Test data rows* (CSV) run a test's steps once per row. Each row reports on its own, and a
  failing row skips only its own remaining steps.
- **Keep going** after a failure, for a whole test or a whole suite. A snippet step marked *keep going* now passes
  that on to its own steps.
- **Scheduled suite runs** (hourly, daily at an hour, weekly on a day) and **failure alerts** to chosen users through
  Frappe's notification bell.
- **Settings page** (`/studio/settings`): retention, defaults for new suites, MCP server status.
- **Retention:** keep the last *N* runs per test and delete runs older than *D* days, with their screenshots, traces and
  videos. Runs nightly and with *Clean up now*.
- **Video recording** of whole runs (suite setting), played on the run report.
- **Data checks:** report-based guards with a row limit, nightly and on-demand runs, and a before/after comparison of
  two runs (added, removed, changed rows).
- **Known failure** on a step: an expected failure is recorded as *Known Issue* (amber) and the run goes on. A different
  failure stays red. A fixed one says so.
- **Self-healing selectors** for element actions (never for assertions), with a suggested new selector.
- **Read-only suites:** the browser blocks write calls and the run lists them. *Also allow* takes a suite's own read
  calls.
- **Run as each user:** one test, run once per user, through sessions made on the server. System Manager only.
- **Step timing trends** on the run report, and *slow* warnings for steps that use more than 70 % of their timeout.
- **MCP server:** an HTTP mode (`--http`) with a bearer token, plus the tools `create_suite`, `run_report`,
  `run_data_checks` and `add_comment`. Run results include the video link.
- **Detached runs** (`run_test_case(detached=1)`): a caller that holds a worker no longer waits on its own run. Data
  checks can run inline (`wait=1`) for the same reason.
- A Test Studio icon on the Desk apps screen, and a matching favicon.
- *Suite settings* in a test's ⋯ menu and its breadcrumb.

### Changed
- `engine.run_case` returns `(status, error, trace, video)`.
- Steps that open a page (`goto`, `login`, `logout`, `new_doc`) wait at least 30 s. Other steps keep the suite
  timeout.
- When a suite records video, the trace leaves out its own screen recording (it was most of the trace's size).
- MCP `create_suite` takes `description` and `settings` (any of the suite's own settings) instead of a ticket.
  `ticket_note` is replaced by the general `add_comment(doctype, name, text)`.
- The step vocabulary lives in `test_studio/vocab.py` and is shared by the MCP server and the app.

### Fixed
- A trace or video over the site's file size limit no longer turns a finished run into *Error*. The run keeps its
  result and says which file was not saved.
- Suite settings are reachable from inside a test.
- The phone layout of the Data checks and Settings pages, and the menu button covering page titles on phones.

## [0.0.1] - 2026-11-09

### Added
- Test Suite, Test Case, Test Snippet, Test Pipeline, Test Run and Pipeline Run doctypes.
- The `/studio` UI: test workspace with a live browser, recorder, debugger with breakpoints, run reports and pipelines.
- Frappe-aware actions (`login`, `new_doc`, `set_field`, `save`, `workflow`, `expect_status`, `create_from`) next to
  the Playwright actions.
- Snippets with inputs and defaults, variables and encrypted secrets, the built-in `{{today}}`.
- Export to a Playwright test file.
- MCP server (stdio) for AI agents.
- Email and SMS blocker for test systems.
