<p align="center">
  <img src="test_studio/public/images/test-studio-logo.svg" width="72" alt="Test Studio">
</p>

<h1 align="center">Test Studio</h1>

<p align="center"><b>Browser tests for Frappe and ERPNext that read like sentences, run in a real browser, and explain themselves when they fail.</b></p>

<p align="center">
  Frappe v16 · Playwright · Vue 3 · MIT
</p>

---

```
 Log in as {{manager_user}}
 New Sales Invoice
 Set Customer to {{customer}}
 Set items[1].item_code to {{item}}
 Save
 Workflow: Submit for Approval
 Status should be Pending Approval            ✓ passed in 9.4s · video · trace
```

Test Studio is a test lab that lives inside your Frappe site. You build tests from plain steps (*set a field*,
*run a workflow action*, *the status should be…*) instead of brittle CSS. Run them in Chromium, Firefox or WebKit
and watch them live. When something breaks, you get the step, Frappe's own error message, a screenshot and a video.
It also checks your **data**, not only your screens, and it opens itself to **AI agents** through MCP, so an agent
can write, run and fix tests too.

## Why it is different

- **Frappe-aware steps.** `set_field` finds a field by label or fieldname, opens its tab or collapsed section, and
  handles links, selects, dates and child table rows (`items[2].qty`). `workflow`, `save`, `expect_status` and
  `create_from` speak Desk, so tests survive layout changes.
- **Failures explain themselves.** You get the failing step in words, the dialog Frappe showed ("On screen: …"), a
  screenshot, an optional **video** of the whole run, and a Playwright trace.
- **It knows what is already broken.** Mark a step with the **known failure** text it currently fails with. The run
  turns amber (*Known Issue*), not red, and goes red again the moment the failure changes. When the bug is fixed, the
  step tells you to remove the mark.
- **It heals itself, carefully.** When a click or an input loses its selector after a UI change, Test Studio finds the
  same element by what it looked like on the last passing run, carries on, and suggests the new selector.
  Assertions are never healed: that would hide a real failure.
- **It tests the data too.** *Data checks* turn any report into a guard ("this must stay empty"), run nightly, and
  compare two runs row by row: added, removed, changed. That is how you rehearse a fix before it reaches production.
- **It is safe on a live site.** A read-only suite blocks every save, submit, cancel, delete and email call from the
  browser, and lists what it blocked.

## A quick tour

| Where (`/studio`) | What you do there |
|---|---|
| **Tests** | Build tests step by step, with a live browser beside you. Record clicks, set breakpoints, debug. |
| **Snippets** | Reusable blocks ("Log in", "Create an approved order") with inputs, used like functions. |
| **Runs** | Every run, with a step timeline, screenshots, a video player, a trace download, and each step's time over the last runs. |
| **Pipelines** | Suites in stages (smoke, then regression). A failing stage can stop the rest. |
| **Data checks** | Report-based guards, nightly runs, and the before/after comparison. |
| **Settings** | Retention of old runs, defaults for new suites, MCP server status. |

## Features

### Building tests
- **29 sentence-like actions:** `login`, `new_doc`, `set_field`, `save`, `workflow`, `expect_status`,
  `create_from`, `run_snippet`, `assert_*`, `store_*`, `goto`, `click`, `fill`, `wait_for`, `screenshot` and more.
  Any Playwright selector works where a selector is needed.
- **Variables everywhere:** `{{customer}}`, suite variables, test overrides, snippet inputs, the values a step
  remembered (`store_text`), and the built-in `{{today}}` in the site's date format. **Secrets** are encrypted,
  masked as `••••` in every result, and exported as `process.env[...]`.
- **Data-driven tests:** paste a CSV table under *Test data rows*. The steps run once per row, each row reports on its
  own, and a failing row does not stop the others.
- **Keep going:** per step, per test or per suite, so one failure does not hide the rest.
- **Snippets with inputs**, nested snippets (cycles are refused). Renaming a snippet updates the tests that use it.
- **Run as each user:** run one test signed in as several users and see who can do what. The sessions are made on the
  server, so no passwords are needed, and only a System Manager can start them.

### Running
- **Chromium, Firefox, WebKit**, headless, with any viewport.
- **Live view and debugger:** watch the browser, pause at breakpoints, step through.
- **Suites, pipelines and schedules:** run a suite hourly, daily or weekly. Failures go to the users you name, through
  Frappe's notification bell.
- **Evidence:** a screenshot on failure or after every step, a **video** of the whole run, and a **Playwright trace**.
  A file that is too big to keep never turns a finished run into an error.
- **Sensible timeouts:** opening a page gets at least 30 s, because a cold or busy server is not a test failure.
  Clicks and checks keep the suite's shorter limit, so wrong assertions still fail fast. Steps that use more than
  70 % of their time are flagged as *slow*.
- **Retention:** keep the last *N* runs per test and delete runs older than *D* days, files included, every night or
  on demand.

### Checking data
- A **Data Check** is any report plus filters plus the most rows it may return (0 means "must be empty"). Filters can use
  `{{today}}`.
- Checks run on the server, nightly or on demand. Anything a report writes is rolled back.
- **Before and after:** compare two check runs. Rows are matched on their text columns, so a changed amount shows as
  *changed*, not as removed plus added.

### Working with AI agents (MCP)
Test Studio ships an [MCP](https://modelcontextprotocol.io) server, `mcp/test_studio_mcp.py`, with 18 tools: learn
the vocabulary, list and create suites, tests and snippets, run tests and read every step, run reports and data
checks, and comment on any document.

```
AI client (Claude Code, QCS Flow, …) ──MCP──▶ test_studio_mcp.py ──Frappe REST + API key──▶ your site
```

- **stdio** for local clients such as Claude Code: `python mcp/test_studio_mcp.py`
- **HTTP** for other services: `python mcp/test_studio_mcp.py --http --port 8765`. It listens on 127.0.0.1 only and
  every request must carry `Authorization: Bearer <TEST_STUDIO_MCP_TOKEN>`.
- The server has no powers of its own. It acts with the permissions of its API key's user. Test runs it starts go
  outside the worker queue, so an agent that holds a worker never waits on itself.

An example of what this allows: a helpdesk automation (any MCP-capable workflow engine) gives an agent these tools.
For each new ticket, the agent creates a suite, writes tests that reproduce the report, investigates and re-tests
until the result is clear, and leaves a comment with the verdict, the evidence, the runs and a video link.
Test Studio itself knows nothing about tickets.

## Install

```bash
bench get-app <this repo>
bench --site <site> install-app test_studio
env/bin/python -m playwright install --with-deps chromium   # add firefox / webkit if you use them
bench build --app test_studio
```

Open **/studio**, or the Test Studio tile on the Desk apps screen. Give testers the **Test Studio User** role; they
do not need to be System Managers. Data checks, Settings and *Run as each user* stay System Manager only.

**Testing on a copy of production data?** Stop the copy from emailing or texting real people:

```bash
bench --site <test-site> set-config test_studio_block_outgoing 1
```

Email is then muted (it still queues, so you can read it in Email Queue) and SMS is logged instead of sent. Without
this setting Test Studio leaves the site's email and SMS alone, so it is safe to install on a live site.

Runs use the `long` queue, so a worker must be running (`bench start` in development); in production give test runs
a worker of their own. Scheduled suites and nightly checks need the site's scheduler
(`bench --site <site> enable-scheduler`).

Want something to play with? `bench --site <site> execute test_studio.demo.create` adds a demo suite and pipeline
against the Playwright TodoMVC page.

## Security notes

- A `login` step checks the password on the server and gives the browser a session, so passwords are never typed
  into the page and never appear in a trace or video. A `fill` step that types a secret into some other field is
  recorded in the trace like any other input: prefer `login`, and treat traces as sensitive.
- Runs started outside the worker queue (agents, MCP, debugging) each start a browser. **Settings → Most runs at
  once** limits them (3 by default).
- The MCP HTTP server listens on 127.0.0.1 and needs its token. It acts with its API key user's permissions.

## Configure

| What | Where |
|---|---|
| Site, browser, timeout, viewport, trace, video, screenshots, read-only, keep going, schedule, alerts, variables | **Suite settings** (a suite's ⚙, or a test's ⋯ menu) |
| Retention, most runs at once, defaults for new suites, MCP status | **Settings** (`/studio/settings`) |
| Block email and SMS on a test copy | `bench --site <site> set-config test_studio_block_outgoing 1` |
| Known failure, timeout, keep going for a single step | The step's *advanced options* |
| MCP server address, API key, HTTP token | `~/.config/test-studio/mcp.env` (`TEST_STUDIO_URL`, `TEST_STUDIO_API_KEY`, `TEST_STUDIO_API_SECRET`, `TEST_STUDIO_MCP_TOKEN`) |
| Start the HTTP MCP server with bench | A Procfile line: `test_studio_mcp: ./env/bin/python apps/test_studio/mcp/test_studio_mcp.py --http --port 8765` |
| Largest trace or video kept | Frappe **System Settings → Max File Size** |

## How it is built

```
frontend/ (Vue 3 + Tailwind, served at /studio)
   │  whitelisted API
test_studio/
   ├─ studio.py    API for the UI: tree, runs, live sessions, settings, retention
   ├─ runner.py    run lifecycle: queue or detached process, sessions, files, alerts, schedule
   ├─ engine.py    framework-free: steps, variables, snippets, data rows, Playwright, healing, read-only guard
   ├─ checks.py    data checks and before/after comparison
   └─ vocab.py     the step vocabulary, shared with the MCP server
mcp/test_studio_mcp.py   MCP server (stdio or HTTP), talks to the site over REST
```

`engine.py` imports nothing from Frappe, so it is unit-tested against a local HTML page.

## Development

```bash
cd apps/test_studio
../../env/bin/python -m unittest test_studio.tests.test_engine test_studio.tests.test_checks test_studio.tests.test_schedule
cd mcp && ../../../env/bin/python test_mcp.py
cd ../frontend && npm install && npx vite build
```

See [CHANGELOG.md](CHANGELOG.md) for what changed.

## License

MIT
