# Golden fixtures

What the **original** pilot code produced, recorded so that `finagent` can be checked against the original behaviour without
the original project. `make_golden.py` made every file from the original code and data (provenance only: it needs the
original project, so the tests never run it). It ran offline: the HTTP transport was a scripted fake, socket connects were
refused, the only API key was the dummy value `DUMMY`, time ran on a virtual clock, and no file of the original project was
written. Two runs give byte-identical files.

| file | size | content | used by |
|---|---|---|---|
| `expected_hashes.json` | 12 KB | sha256 of the prompt texts, the 32 tool schemas, the 66 example files, and per day the anchor, decision time and readings block | L0 prompt, data and readings checks |
| `golden_tools.json.gz` | 123 KB | 1,896 tool calls (6 days x 79 calls x 4 arms), 24 stateful call sequences, 60 `submit_decision` echoes | L0 golden tool outputs |
| `golden_session.json.gz` | 114 KB | 17 complete harness runs with a scripted model: every request, every tool result, the session and the record | harness session loop, record |
| `golden_requests.json` | 284 KB | the exact HTTP requests for each of the 5 models, and the retry rules of the 3 provider clients | providers |
| `golden_codex_configs.json` | 22 KB | `codex_config()` inputs, its output and the recorded `codex_config.toml` for one coding run per model | coding agent config |

## Conventions

- UTF-8 JSON, indent 1. The fixtures' own keys are sorted. Objects captured from the original code (records, sessions, tool
  states, tool arguments, request headers) keep the key order that code produced, because the bytes of `record.json` and of
  every request depend on it.
- Tool outputs, request bodies and reply bodies are the exact strings.
- Timing fields are dropped: `wall_s` and `finished_epoch` from records, `s` from `session.ctx.requests[]`, `t` from
  `session.ctx.raw_responses[]`.
- Host values are the recorded host's (vLLM ports 18580/18581/18582, relay ports 18590-18595, `WS_ROOT=/srv/shared_home/lmz/cxpw`).
  Compare with the new code configured from `setup/host.recorded.env`.

## `expected_hashes.json`

- `texts.<name>` = `{chars, sha256}` of the exact text, no newline added: `harness_system` (`e992af5a…`), `coding_system`
  (`84691352…`), `agent_prompt`, `permissions`, `reminder`.
- `tools_sha256` = sha256 of `json.dumps(tools, sort_keys=True)` over the 32 harness tool schemas (`32860efa…`); `n_tools` = 32.
- `examples` maps `<day_id>/{prices.csv,news.csv,account.json}` and `<day_id>/<ARM>/{harness_prompt.txt,task.md}` to sha256:
  66 entries, which is the layout of `data/prompts/examples/`. The generator checked that the hashes in the original `prompt_check.json`
  and the bytes of the original `examples/` files agree.
- `days.<day_id>`: `ticker`, `t`, `decision_time` (D(t) as `YYYYMMDDTHHMMSS`, New York time), `anchor_sha256`
  (`data/anchors/<day_id>.json.gz`), `block_sha256` (the registered readings block), `block_sha256_by_arm.<ARM>` (the block
  after the arm rewrite).
- `rewrite_check` = `{n_checks: 456, n_with_problems: 0}`.

## `golden_tools.json.gz`

The tool outputs a session receives. Every call follows the harness path of the original code: a fresh anchor state of the day
(`state_from_json` of its anchor), a fresh `FULL` view of the stock's news cache, `as_of` = day t, and the original run-tool
wrapper of the arm. One call never sees the state of another call.

- `calls[]` = `{day_id, arm, tool, args, output_raw, output_cut[, state_after]}`.
  - `output_raw` is the run-tool output after the arm rewrite. For `ORIG` it is the toolbox's own output.
  - `output_cut` = `output_raw[:2500]` (`tool_result_chars`). This is what the model received.
  - `state_after` is the toolbox state after the call. It is present only when the call changed the state (`memory_write`
    with a note).
- The 79 calls per day and arm (`make_golden.VARIANTS`):
  - each of the 31 tools with `{}`;
  - 47 variants that cover every parameter of every tool, numbers given as strings (`{"days": "5"}`), a tool error
    (`get_rsi {"period": 0}`), the day's own ticker for the earnings tools, and an ignored argument on a block tool (the
    rewrite applies to any call of a block tool);
  - the misspelt tool `get_memory_read`, which one recorded session called.
- `sequences[]` = `{day_id, arm, calls[], state_after}`: 9 calls on one state, in order (`memory_write` x2, `memory_search` x2,
  `memory_read`, `simulate_order`, `get_portfolio`, `get_trade_history`, `get_volatility_stats`).
- `submit_echoes[]` = `{day_id, args, echo}`: the reply the session loop gives to `submit_decision(args)` on the day's anchor
  book (6 days x 10 argument sets: on and off target, Buy/Sell/Hold, clamped orders, a string share count, a non-numeric
  target, `{}`).

## `golden_session.json.gz` and `golden_requests.json`

Each harness run is `{day_id, arm, model, run, exchanges, session, record}` (plus `scenario` in sessions). It went through the
original `harness_agent.run_openai`, unchanged, against scripted model replies.

- `run` is the run-list row (`run_id`, `seed`, ...).
- `exchanges[]` = `{request: {method, url, headers, timeout, body}, response: {status, body}}`, in order.
  - `request.body` is the exact JSON text sent, so it holds the messages of every turn.
  - `response` is the scripted reply. Feed it back to replay the run.
  - `headers` are as sent, with the `Authorization` value replaced by `<redacted>`. `User-Agent` and `Accept-Encoding` come from
    requests 2.34.2 / urllib3 2.8.0 of the runner environment.
- `session` is the content of `session.json.gz` and `record` the content of `record.json`, both without the timing fields.

`golden_session.json.gz` holds these runs, all with model `qwen3_8b` (vLLM):
- `sessions[]`: 12 runs (6 days x `ORIG`, `UNIT5D`) of the script `tools_then_submit`. Turn 1 calls 3 tools, including a block
  tool. Turn 2 calls 3 tools, including `memory_write`. Turn 3 calls `submit_decision` off target plus one more tool. Turn 4
  calls `submit_decision` again: the last submission wins.
- `edge_cases[]`: 5 runs on `VST_2026-05-06`, `ORIG`:
  - `turn_cut_by_token_cap`;
  - `reminder_after_no_call`;
  - `gives_up_after_reminder`;
  - `final_reminder_after_ten_turns` (11 requests; the last one uses seed + 99);
  - `malformed_arguments` (invalid or non-object JSON arguments).

`golden_requests.json` has two parts:
- `conversations[]`: one run per model (`qwen3_8b`, `qwen35_9b`, `qwen38_27b`, `deepseek`, `kimi`) on `VST_2026-05-06`, `UNIT5D`.
  Turn 1 reasons and calls `get_volatility_stats` and `get_rsi`. Turn 2 submits. So the second request carries the assistant
  tool-call turn; for DeepSeek and Kimi it also carries `reasoning_content`, passed back. `qwen38_27b` runs with the
  `run_qwen38` additions: `max_tokens` 8192, `ctx.raw_choices`, and the record fields `served_max_model_len`, `gpu_index`,
  `max_tokens_per_turn`.
- `retries[]` = `{model, scenario, replies, repeat_last, n_requests, sleeps, outcome, request_entries, n_raw_responses}`.
  - Each entry is one `harness_agent.chat` call for `qwen3_8b`, `deepseek` or `kimi` against a sequence of HTTP outcomes:
    `ok`, `busy_then_ok`, `client_error_then_ok`, `client_error_three_times`, `connection_error_then_ok` and
    `unavailable_until_give_up`.
  - A reply `{"error": "ConnectionError"}` means the transport raised `requests.ConnectionError`. With `repeat_last`, the last
    reply repeats forever.
  - Time advances only by the recorded `sleeps`, so `unavailable_until_give_up` ends at the 6 h (vLLM) or 1 h (API) limit.
  - `outcome` is `{finish_reason}` or `{raised: "<type>: <message>"}`. `request_entries` is the per-request accounting
    without `s`.

To replay, replace `requests.adapters.HTTPAdapter.send` with a fake. The fake returns the next `response` as a
`requests.Response` (`status_code`, `_content` = body bytes, `encoding` utf-8) and raises `requests.ConnectionError` for an
`error` reply. Then run the new code for the same model, day, arm and seed. Compare each request's `url`, `timeout`, `body`
(exact text) and headers, and then the session and the record. For `retries`, also patch `time.time` and `time.sleep` with a
clock that only the sleeps advance.

## `golden_codex_configs.json`

- `configs[]`: the first `ORIG` run on `MCHP_2026-08-07` for each model. Each entry holds:
  - the inputs: `model`, `model_id`, `label`, `rid`, `relay_port`, `ws_root`, `home`, `tmp`, `agent_path`, `context_window`,
    `reasoning_effort`, `run_id`;
  - `codex_config_text`, the original `codex_config(model, rid, home, tmp)`;
  - `recorded_text`, the run's `codex_config.toml`. The two texts are identical.
- `n_recorded_identical` = 150: the original function regenerates all 150 recorded configs of the five models exactly.

## Regenerating

```
$ORIG/.venv/bin/python -B tests/fixtures/make_golden.py $ORIG tests/fixtures
```

`$ORIG` is the original project folder. The script sets `NEWSAGENT=1 TOOL_HORIZON=5d CUDA_VISIBLE_DEVICES=` itself. It takes
about 25 s on CPU.
