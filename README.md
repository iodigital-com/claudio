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
> This works well for a single key per machine, but it can't be combined with an auth token. claudio adds value when you manage multiple clients with different keys or need per-project env vars beyond just the API key.

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

# Print the API key for the last-selected project (for use as apiKeyHelper)
claudio get-key

# Print the API key for a specific project
claudio get-key --project 'Customer 1'

# Help
claudio --help
```

### Using Claudio with the VS Code Claude Extension

To use `claudio` with the VS Code Claude extension, configure `apiKeyHelper` in your Claude settings (`~/.claude/settings.json` or `.claude/settings.local.json`):

```json
{
  "apiKeyHelper": "claudio get-key"
}
```

This will automatically use the last project you selected with `claudio`.

#### Pinning a project per workspace

If you want a specific workspace to always use one project (regardless of what you last selected), pin it in that workspace's `.claude/settings.local.json`:

```json
{
  "apiKeyHelper": "claudio get-key --project 'Customer 1'"
}
```

> **Note:** Do not set `ANTHROPIC_API_KEY` or `ANTHROPIC_AUTH_TOKEN` in `claudeCode.environmentVariables` or your shell profile — environment variables take precedence over `apiKeyHelper` and will cause a conflict warning. Keep all tokens exclusively in your `claudio.settings.json`.

### CLI

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
  - **`env`** (object, optional) — key-value pairs of environment variables. These are **merged** into the `env` of the Claude Code config, overriding only the keys you specify. Values starting with `op://` are resolved via the 1Password CLI at runtime (see below).

Example config:

```json
{
  "projects": [
    {
      "name": "Customer 1",
      "env": {
        "ANTHROPIC_API_KEY": "op://....."
      }
    },
    {
      "name": "Customer 2",
      "env": {
        "ANTHROPIC_API_KEY": "sk-..."
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
      "name": "Customer 1",
      "env": {
        "ANTHROPIC_API_KEY": "op://....."
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
        "ANTHROPIC_API_KEY": "op://<vault>/<item>/<attribute>"
      }
    }
  ]
}
```

> You can use different 1Password item types if you want and create your own (password-typed) attributes if you want.

Example1: the default for a "password" type item
```json
"ANTHROPIC_API_KEY": "op://Employee/Bonzai API key clientX/password"
```
Example2: the "password" type with a custom password-type attribute
```json
"ANTHROPIC_API_KEY": "op://Employee/Bonzai API keys/clientX"
```
Example3: the default for a "API Credential" type item
```json
"ANTHROPIC_API_KEY": "op://Employee/Bonzai API key ClientX/referentie"
```

When `claudio` detects an `op://` value, it resolves it via the [1Password CLI](https://www.1password.dev/cli/get-started) (`op read`) before passing the token to Claude Code. Everyone at iO has access to 1Password, so this is the preferred setup.

You do need to setup 1Password CLI for this, see: https://www.1password.dev/cli/get-started


