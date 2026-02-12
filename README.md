# claudio

CLI wrapper for [Claude Code](https://docs.anthropic.com/en/docs/claude-code) that lets you switch between projects with different API keys (or other env vars) before launching `claude`.

## The Problem

Claude Code's `env` config uses a "highest-precedence layer wins" approach — you can't override specific keys without replacing the entire object. This makes it hard to manage multiple projects that share most env vars but differ in one or two (e.g. `ANTHROPIC_AUTH_TOKEN`).

## This Solution

`claudio` takes the `env` from your highest-precedence Claude config and **merges the selected project's keys on top**. You only specify the vars that differ per project, and the rest are preserved.

## Prerequisites

- [uv](https://docs.astral.sh/uv/) package manager

## Installation

```sh
uv tool install . --reinstall
```

## Usage

```sh
# Launch with project selection
claudio

# Pass arguments through to claude
claudio --model claude-4-5-sonnet -p "hello"

# Help
claudio --help
```

When you run `claudio`:

1. It discovers your `claudio` config (highest precedence wins).
2. If there's only **one** project, it's selected automatically.
3. Otherwise you're prompted to pick one (the last-used project is the default).
4. The selected project's env is merged into your Claude config.
5. `claude` is launched with any extra CLI arguments you passed.

If no `claudio` config exists, `claude` is launched directly.

## Configuration

Create a `claudio.settings.json` (shared) or `claudio.settings.local.json` (git-ignored, personal) in any of these locations (same hierarchy as Claude Code):

| Scope         | Path                                  |
| ------------- | ------------------------------------- |
| User          | `~/.claude/claudio.settings.json`     |
| Project       | `.claude/claudio.settings.json`       |
| Project local | `.claude/claudio.settings.local.json` |

Example config:

```json
{
  "projects": [
    {
      "name": "Customer 1",
      "env": {
        "ANTHROPIC_AUTH_TOKEN": "sk-..."
      }
    },
    {
      "name": "Customer 2",
      "env": {
        "ANTHROPIC_AUTH_TOKEN": "sk-..."
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
        "ANTHROPIC_AUTH_TOKEN": "sk-ant-..."
      }
    }
  ]
}
```

Because there's only one project, `claudio` will select it automatically — no prompt needed.

### Config Schema

- **`projects`** — array of project objects:
  - **`name`** (string, required) — display name for the project.
  - **`env`** (object, optional) — key-value pairs of environment variables. These are **merged** into the `env` of the Claude Code config, overriding only the keys you specify.
