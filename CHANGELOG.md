# Changelog

## [0.2.1]

### Added
- `claudio get-key` command — prints the resolved API key for the last-selected project (or a specific project via `--project`). Intended for use as `apiKeyHelper` in Claude settings to authenticate the VS Code extension.

### Fixed
- `claudio get-key` now works on Windows — 1Password CLI (`op`) was not found due to a missing `shell=True` on Windows subprocesses.
- Single-project configs now persist `lastProject` on launch, so `claudio get-key` can always resolve the active project without requiring a prior interactive selection.
- When `apiKeyHelper` is configured in Claude settings, claudio no longer injects `ANTHROPIC_API_KEY` / `ANTHROPIC_AUTH_TOKEN` as environment variables on CLI launch. This eliminates the "Both apiKeyHelper and ANTHROPIC_API_KEY set" conflict warning.

  > **Migration note:** If you use a custom `apiKeyHelper` (not `claudio get-key`) alongside tokens in your claudio project config, the tokens will no longer be injected — `apiKeyHelper` takes precedence. Remove the custom `apiKeyHelper` or move the tokens out of claudio config if needed.
