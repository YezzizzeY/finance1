"""Framework 2, the coding agent: Codex CLI in a point-in-time workspace, behind a sandbox, a relay and a leakage audit.

  workspace  the files of (day, arm) and where a run lives      codex  config.toml, one sandboxed run, batches, the audit canary
  sandbox    Landlock + seccomp launcher (a standalone script)  relay  the agent's only network path; holds the API key
  audit      the leakage verdict of a run, and the re-audit of saved runs (`finagent audit`)
"""
