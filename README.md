# claudio

CLI wrapper for [Claude Code](https://docs.anthropic.com/en/docs/claude-code) that lets you switch between projects with different API keys (or other env vars) before launching `claude` and retrieving them from 1Password, before launching claude.

## The Problem

When working for multiple clients, you often need to switch between different Anthropic API keys. Claude Code doesn't provide a way to select a named project configuration at launch — you'd have to manually update your config or environment before each session.

On top of that, storing API keys as plaintext in config files is a supply chain risk.

## This Solution

`claudio` lets you define named project profiles, each with their own env vars. At launch you pick a project and its env is merged into your Claude config for that session. API keys are stored securely in 1Password and resolved at runtime — never written to disk in plaintext.

> Claude Code also supports [`apiKeyHelper`](https://code.claude.com/docs/en/settings#available-settings) — a shell command that returns an API key at runtime, so you can pull it from 1Password yourself:
> ```json
> { "apiKeyHelper": "op read op://Personal/Anthropic/credential" }
> ```
> This works well for a single key per machine, but it triggers a new 1Password biometric prompt on every invocation and can't be combined with a bearer auth token. claudio adds value when you manage multiple clients with different keys, use a company proxy that requires bearer auth, or need per-project env vars beyond just the API key.

## Prerequisites

- Mac/Linux: [homebrew](https://brew.sh/) package manager (run once ever):
  ```sh
  brew tap iodigital-com/io
  ```
  ```sh
  brew trust --tap iodigital-com/io
  ```

  (or) [uv](https://docs.astral.sh/uv/) package manager
- Windows: [uv](https://docs.astral.sh/uv/) package manager

## Installation
### Mac/Linux
1. brew install claudio
1. Run `claudio` anywhere

### Windows
1. Clone the repo
1. Run `uv tool install . --reinstall` from the repo root
1. Run `claudio` anywhere

## Usage

```sh
# Launch with project selection
claudio

# Pass arguments through to claude
claudio --model claude-4-5-sonnet -p "hello"

# Select project by name (non-interactive)
claudio --project "Klant A"

# Check config and credentials health
claudio doctor
claudio doctor --project "Klant A"

# List configured projects
claudio projects

# Print the currently selected project name
claudio current

# VS Code / Cursor setup
claudio setup vscode --print       # show what to add
claudio setup vscode --workspace   # write to .vscode/settings.json
claudio setup cursor --print
claudio setup cursor --workspace

# Help
claudio --help
```

When you run `claudio`:

1. It discovers your `claudio` config (highest precedence wins).
1. If there's only **one** project, it's selected automatically.
1. Otherwise you're prompted to pick one (the last-used project is the default).
1. The selected project's env is retrieved from 1Password and merged into your Claude config.
1. `claude` is launched with any extra CLI arguments you passed.

If no `claudio` config exists, `claude` is launched directly.
Note that even though `claudio` works with API keys specified in the settings files for backward compatibility, the 1Password store is highly preferred.

## Configuration

Create a `claudio.settings.json` (shared) or `claudio.settings.local.json` (git-ignored, personal) in any of these locations (same hierarchy as Claude Code):

| Scope         | Path                                  |
| ------------- | ------------------------------------- |
| User          | `~/.claude/claudio.settings.json`     |
| Project       | `.claude/claudio.settings.json`       |
| Project local | `.claude/claudio.settings.local.json` |

### Config Schema

- **`projects`** — array of project objects:
  - **`name`** (string, required) — display name for the project.
  - **`env`** (object, optional) — key-value pairs merged into the Claude Code `env`. Values starting with `op://` are resolved via the 1Password CLI at runtime.

### Supported env vars

| Variable | Purpose |
| --- | --- |
| `ANTHROPIC_AUTH_TOKEN` | Bearer token — for company proxies or OAuth tokens |
| `ANTHROPIC_API_KEY` | API key — for direct Anthropic access or proxies that require one |
| `ANTHROPIC_BASE_URL` | Endpoint URL — required when routing through a company proxy |

Set `ANTHROPIC_AUTH_TOKEN` **or** `ANTHROPIC_API_KEY`, not both. If both are present, `ANTHROPIC_AUTH_TOKEN` takes precedence in Claude Code. Use `claudio doctor` to catch conflicts.

### Why prefer ANTHROPIC_AUTH_TOKEN for company proxies?

Company proxies typically issue short-lived bearer tokens (OAuth access tokens, SSO-issued JWTs) rather than static API keys. Bearer tokens:
- Are issued per-user and can be revoked without rotating a shared key
- Are the correct HTTP auth mechanism (`Authorization: Bearer <token>`)
- Work with proxies that forward to Anthropic on your behalf

Use `ANTHROPIC_API_KEY` only when the proxy specifically requires an API key format, or for direct Anthropic access.

### Examples

**Company proxy (bearer token):**

```json
{
  "projects": [
    {
      "name": "Klant A",
      "env": {
        "ANTHROPIC_BASE_URL": "https://proxy.company.com",
        "ANTHROPIC_AUTH_TOKEN": "op://Employee/Klant A/token"
      }
    }
  ]
}
```

**Direct Anthropic API:**

```json
{
  "projects": [
    {
      "name": "Personal",
      "env": {
        "ANTHROPIC_API_KEY": "op://Personal/Anthropic/credential"
      }
    }
  ]
}
```

**Multiple clients, mixed setup:**

```json
{
  "projects": [
    {
      "name": "Klant A",
      "env": {
        "ANTHROPIC_BASE_URL": "https://proxy.klantA.com",
        "ANTHROPIC_AUTH_TOKEN": "op://Employee/Klant A/token"
      }
    },
    {
      "name": "Personal",
      "env": {
        "ANTHROPIC_API_KEY": "op://Personal/Anthropic/credential"
      }
    }
  ]
}
```

### Pinning a project per repo

If you always use the same project in a given repo, create a `.claude/claudio.settings.local.json` in your workspace with a single project:

```json
{
  "projects": [
    {
      "name": "Klant A",
      "env": {
        "ANTHROPIC_BASE_URL": "https://proxy.klantA.com",
        "ANTHROPIC_AUTH_TOKEN": "op://Employee/Klant A/token"
      }
    }
  ]
}
```

Because there's only one project, `claudio` will select it automatically — no prompt needed.

### Storing API keys securely with 1Password

Storing API keys as plaintext in config files is a supply chain risk — if a malicious package or tool reads your filesystem, your keys are exposed. The recommended approach is to store API keys in 1Password and reference them using the `op://` URI scheme:

```json
{
  "projects": [
    {
      "name": "Customer 1",
      "env": {
        "ANTHROPIC_AUTH_TOKEN": "op://<vault>/<item>/<attribute>"
      }
    }
  ]
}
```

> You can use different 1Password item types if you want and create your own (password-typed) attributes if you want.

Example1: the default for a "password" type item
```json
"ANTHROPIC_AUTH_TOKEN": "op://Employee/Bonzai API key clientX/password"
```
Example2: the "password" type with a custom password-type attribute
```json
"ANTHROPIC_AUTH_TOKEN": "op://Employee/Bonzai API keys/clientX"
```
Example3: the default for a "API Credential" type item
```json
"ANTHROPIC_AUTH_TOKEN": "op://Employee/Bonzai API key ClientX/referentie"
```

When `claudio` detects an `op://` value, it resolves it via the [1Password CLI](https://www.1password.dev/cli/get-started) (`op read --no-newline`) before passing the token to Claude Code. Identical `op://` refs within one run are cached so you get at most one biometric prompt per unique secret. Everyone at iO has access to 1Password, so this is the preferred setup.

You do need to setup 1Password CLI for this, see: https://www.1password.dev/cli/get-started

## VS Code setup

> **claudio does not replace the Claude Code extension or its sign-in.** It only
> injects your project's credentials into the environment before Claude Code
> starts. You still install the extension and authenticate as usual — claudio
> just makes the right `ANTHROPIC_*` env vars available for each project (e.g. a
> company proxy `ANTHROPIC_BASE_URL` + `ANTHROPIC_AUTH_TOKEN`).

Full setup, in order:

1. **Install the Claude Code extension** in VS Code (Extensions view → search
   "Claude Code" → Install). This is required — claudio does not install it.
2. **Configure the wrapper** so secrets are resolved automatically on every
   session:
   ```sh
   claudio setup vscode --workspace
   ```
   This creates `~/.claude/claudio-wrapper` (a global shell shim) and writes
   `claudeCode.claudeProcessWrapper` to your VS Code user settings
   (`~/Library/Application Support/Code/User/settings.json` on macOS). You only
   need to run this once per machine — the shim works for all repos.
3. **Make sure the project resolves** — either set `CLAUDIO_PROJECT` in the shell
   that launches VS Code, or add a single-project
   `.claude/claudio.settings.local.json` to the workspace (see
   [Non-interactive project resolution](#non-interactive-project-resolution-in-wrapper-mode)).
4. **Restart VS Code** (or run *Developer: Reload Window*) so the setting takes
   effect.
5. **Open the Claude Code panel and authenticate** as you normally would:
   - For a **company proxy**, the injected `ANTHROPIC_BASE_URL` +
     `ANTHROPIC_AUTH_TOKEN` handle auth; you may also need to enable
     *Disable Login Prompt* in the extension settings for third-party providers.
   - For **direct Anthropic access**, sign in with your Claude account, or rely
     on the injected `ANTHROPIC_API_KEY`.

If the Claude panel still shows *Not logged in* / *Please run /login* after this,
see [Troubleshooting the VS Code wrapper](#troubleshooting-the-vs-code-wrapper).

To preview what would be written without making changes:

```sh
claudio setup vscode --print
```

**How it works:** VS Code's `claudeCode.claudeProcessWrapper` setting takes a
single executable path, and the editor invokes it with **its own bundled `claude`
binary as the first argument**. `claudio setup vscode` generates a thin shell
script:

```sh
#!/bin/sh
exec /abs/path/to/claudio wrapper --fallback-claude /abs/path/to/claude "$@"
```

When VS Code launches Claude Code, it runs this shim, which resolves the project
non-interactively and injects the credentials into the environment before
exec-ing Claude Code (secrets never appear in `ps` output). The wrapper **execs
the bundled binary the editor passes in**, so you run the exact Claude Code build
the extension ships; `--fallback-claude` is only used when the editor passes no
binary (e.g. an unsupported platform) or when you run the shim manually.

### Troubleshooting the VS Code wrapper

| Symptom | Cause / fix |
| --- | --- |
| Claude panel shows *Not logged in* / no authentication | The wrapper couldn't inject credentials or the project didn't resolve. Run `claudio doctor` in the workspace, confirm `CLAUDIO_PROJECT` (or a single-project `.claude/claudio.settings.local.json`) is set, then reload the window. |
| Nothing happens / extension can't start | Confirm `~/.claude/claudio-wrapper` exists and is executable, and that `claudeCode.claudeProcessWrapper` in your **user** settings points at it. Re-run `claudio setup vscode --workspace`. |
| Works in terminal but not in the panel | VS Code may not inherit your shell env. Launch it with `code .` from a terminal, or pin the project via `.claude/claudio.settings.local.json`. |

### Non-interactive project resolution in wrapper mode

In wrapper mode, claudio never prompts. Project resolution order:

1. `CLAUDIO_PROJECT` environment variable
2. `--project` flag (if set in the environment that starts VS Code)
3. Single project auto-select (workspace `.claude/claudio.settings.local.json` with one project)
4. Fail with instructions if ambiguous

If the project cannot be resolved, the error message guides you to:
- Set `CLAUDIO_PROJECT` in the shell that launches VS Code
- Or create `.claude/claudio.settings.local.json` with one project
- Or re-run `claudio setup vscode --workspace` which pins the config

## Cursor setup

```sh
claudio setup cursor --workspace
```

As with VS Code, this only injects credentials — you still install the Claude
Code extension in Cursor and sign in there. This writes
`claudeCode.claudeProcessWrapper` to your Cursor user settings instead of VS
Code's. The same `~/.claude/claudio-wrapper` shim is reused, so running both
`setup vscode` and `setup cursor` is safe.

```sh
claudio setup cursor --print   # preview only
```

## Troubleshooting with `claudio doctor`

`claudio doctor` performs a health check on your configuration and exits 1 if any warnings are found.

```
$ claudio doctor

Binaries:
  claude   /usr/local/bin/claude
  op       /usr/local/bin/op

Config:
  .claude/claudio.settings.local.json  [active]
  .claude/claudio.settings.json        [not found]
  ~/.claude/claudio.settings.json      [not found]

1 project(s) configured.

  Klant A
    ANTHROPIC_BASE_URL    (plaintext)
    ANTHROPIC_AUTH_TOKEN  (1Password)

No issues found.
```

Output is always redacted: only variable names and their storage type (`1Password` or `plaintext`) are shown — resolved secret values are never printed.

### Common warnings

| Warning | Fix |
| --- | --- |
| `no credential configured` | Add `ANTHROPIC_AUTH_TOKEN` or `ANTHROPIC_API_KEY` to the project env |
| `both ANTHROPIC_API_KEY and ANTHROPIC_AUTH_TOKEN are set` | Remove one; `ANTHROPIC_AUTH_TOKEN` takes precedence |
| `op not found` | Install the 1Password CLI from https://developer.1password.com/docs/cli/get-started/ |
| `claude not found` | Install Claude Code |

### Notes (non-blocking)

| Note | Meaning |
| --- | --- |
| `ANTHROPIC_AUTH_TOKEN set without ANTHROPIC_BASE_URL` | Usually means you forgot `ANTHROPIC_BASE_URL`; fine if your proxy is set globally |

### Security trade-offs

| Approach | Where secrets live | Risk |
| --- | --- | --- |
| `op://` in config | 1Password vault, resolved at runtime | Low — requires 1Password CLI and biometric |
| Plaintext in config | Config file on disk | Medium — readable by any process with filesystem access |
| Environment variable injection | Process environment, inherited by child | Low — not visible in `ps` output |
