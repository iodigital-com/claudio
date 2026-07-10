# claudio

Manages named API keys for [Claude Code](https://docs.anthropic.com/en/docs/claude-code) and launches `claude` with the right one. Secrets are pulled from 1Password at runtime — nothing stored in plaintext.

## Claude Code

**Install** (Mac/Linux):
```sh
brew tap iodigital-com/io
brew trust --tap iodigital-com/io
brew install claudio
```

Windows: clone the repo and run `uv tool install . --reinstall` from the repo root.

**Create a config** at `~/.claude/claudio.settings.json`:

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

**Run:**
```sh
claudio
```

claudio picks a credentials profile, resolves `op://` secrets from 1Password, and launches `claude`. With one profile it selects automatically; otherwise you get an interactive picker with the last-used profile as default.

Run `claudio doctor` to verify your setup.

> For multiple profiles, per-repo pinning, and advanced config see [Configuration reference](#configuration-reference).

## VS Code

With claudio installed and a config in place (see above), run **once per machine**:

```sh
claudio setup vscode --workspace
```

Restart VS Code. From now on, VS Code launches Claude Code through claudio automatically — credentials are resolved without any prompts.

If you have multiple credentials profiles, pin the right one for a repo by creating `.claude/claudio.settings.local.json` with a single profile (see [Pinning a credentials profile per repo](#pinning-a-credentials-profile-per-repo)).

> Preview what the setup command writes without applying it: `claudio setup vscode --print`

## Cursor

With claudio installed and a config in place, run **once per machine**:

```sh
claudio setup cursor --workspace
```

Restart Cursor. Works identically to the VS Code setup — the same `~/.claude/claudio-wrapper` shim is reused, so running both `setup vscode` and `setup cursor` is safe.

> Preview: `claudio setup cursor --print`

---

## Configuration reference

Create a `claudio.settings.json` (shared) or `claudio.settings.local.json` (git-ignored, personal) in any of these locations (same hierarchy as Claude Code):

| Scope         | Path                                  |
| ------------- | ------------------------------------- |
| User          | `~/.claude/claudio.settings.json`     |
| Project       | `.claude/claudio.settings.json`       |
| Project local | `.claude/claudio.settings.local.json` |

### Schema

- **`projects`** — array of credentials profile objects:
  - **`name`** (string, required) — display name for the credentials profile.
  - **`env`** (object, optional) — key-value pairs merged into the Claude Code `env`. Values starting with `op://` are resolved via the 1Password CLI at runtime.

### Supported env vars

| Variable | Purpose |
| --- | --- |
| `ANTHROPIC_AUTH_TOKEN` | Bearer token — for company proxies or OAuth tokens |
| `ANTHROPIC_API_KEY` | API key — for direct Anthropic access or proxies that require one |
| `ANTHROPIC_BASE_URL` | Endpoint URL — required when routing through a company proxy |

Set `ANTHROPIC_AUTH_TOKEN` **or** `ANTHROPIC_API_KEY`, not both. If both are present, `ANTHROPIC_AUTH_TOKEN` takes precedence in Claude Code. Use `claudio doctor` to catch conflicts.

### Examples

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

### Pinning a credentials profile per repo

If you always use the same credentials profile in a given repo, create a `.claude/claudio.settings.local.json` in your workspace with a single profile:

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

Because there's only one credentials profile, `claudio` selects it automatically — no prompt needed. This is also the recommended way to resolve credentials in VS Code and Cursor wrapper mode.

### Other commands

```sh
# Select credentials profile by name (non-interactive)
claudio --project "Klant A"

# Pass arguments through to claude
claudio --model claude-sonnet-4-5

# List configured credentials profiles
claudio projects

# Print the currently selected credentials profile name
claudio current
```

If no `claudio` config exists, `claude` is launched directly.

## Storing API keys securely with 1Password

Storing API keys as plaintext in config files is a supply chain risk — if a malicious package or tool reads your filesystem, your keys are exposed. Store secrets in 1Password and reference them with the `op://` URI scheme:

```
op://<vault>/<item>/<attribute>
```

**Common patterns:**

```json
"ANTHROPIC_AUTH_TOKEN": "op://Employee/Bonzai API key clientX/password"
```
```json
"ANTHROPIC_AUTH_TOKEN": "op://Employee/Bonzai API keys/clientX"
```
```json
"ANTHROPIC_AUTH_TOKEN": "op://Employee/Bonzai API key ClientX/referentie"
```

> You can use any 1Password item type and create custom (password-typed) attributes.

When `claudio` detects an `op://` value, it resolves it via the [1Password CLI](https://www.1password.dev/cli/get-started) (`op read --no-newline`) before passing the token to Claude Code. Identical `op://` refs within one run are cached so you get at most one biometric prompt per unique secret.

You need the 1Password CLI installed: https://www.1password.dev/cli/get-started

### Security trade-offs

| Approach | Where secrets live | Risk |
| --- | --- | --- |
| `op://` in config | 1Password vault, resolved at runtime | Low — requires 1Password CLI and biometric |
| Plaintext in config | Config file on disk | Medium — readable by any process with filesystem access |
| Environment variable injection | Process environment, inherited by child | Low — not visible in `ps` output |

## How wrapper mode works

When you run `claudio setup vscode --workspace` or `claudio setup cursor --workspace`, claudio:

1. Creates `~/.claude/claudio-wrapper` — a thin shell shim:
   ```sh
   #!/bin/sh
   exec /abs/path/to/claudio wrapper -- /abs/path/to/claude "$@"
   ```
2. Writes `claudeCode.claudeProcessWrapper` pointing to that shim in your user settings:
   - VS Code on macOS: `~/Library/Application Support/Code/User/settings.json`
   - VS Code on Windows: `%APPDATA%\Code\User\settings.json`
   - Cursor: same paths under `Cursor` instead of `Code`

When the IDE launches Claude Code, it runs the shim. The shim resolves credentials non-interactively and injects them into the environment before exec-ing the real `claude` binary — secrets never appear in `ps` output.

### Credentials profile resolution in wrapper mode

In wrapper mode, claudio never prompts. Resolution order:

1. `CLAUDIO_PROJECT` environment variable
2. `--project` flag (if set in the environment that starts the IDE)
3. Single profile auto-select (workspace `.claude/claudio.settings.local.json` with one profile)
4. Fail with instructions if ambiguous

If the profile cannot be resolved, the error message guides you to:
- Set `CLAUDIO_PROJECT` in the shell that launches the IDE
- Or create `.claude/claudio.settings.local.json` with one profile

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
| `no credential configured` | Add `ANTHROPIC_AUTH_TOKEN` or `ANTHROPIC_API_KEY` to the credentials profile env |
| `both ANTHROPIC_API_KEY and ANTHROPIC_AUTH_TOKEN are set` | Remove one; `ANTHROPIC_AUTH_TOKEN` takes precedence |
| `op not found` | Install the 1Password CLI from https://developer.1password.com/docs/cli/get-started/ |
| `claude not found` | Install Claude Code |

### Notes (non-blocking)

| Note | Meaning |
| --- | --- |
| `ANTHROPIC_AUTH_TOKEN set without ANTHROPIC_BASE_URL` | Usually means you forgot `ANTHROPIC_BASE_URL`; fine if your proxy is set globally |