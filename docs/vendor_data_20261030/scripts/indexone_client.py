"""Index One 接口的最小客户端（通过它的 MCP 端点的预览运行取数）。钥匙运行时从 keys.txt 读取。"""
import json, re, time, urllib.error, urllib.request

URL = "https://api.indexone.io/mcp"
_line = next(l for l in open("/srv/shared_home/lmz/ai/keys.txt") if l.lower().startswith("index one"))
_KEY = re.search(r"secret\s*(\S+)", _line).group(1)

def call(name, args, tries=12):
    body = json.dumps({"jsonrpc": "2.0", "id": 1, "method": "tools/call",
                       "params": {"name": name, "arguments": args}}).encode()
    for i in range(tries):
        req = urllib.request.Request(URL, body, {"Content-Type": "application/json",
                                                 "Accept": "application/json, text/event-stream", "x-api-key": _KEY})
        try:
            out = json.load(urllib.request.urlopen(req, timeout=300))
            return json.loads(out["result"]["content"][0]["text"])
        except urllib.error.HTTPError as e:
            if e.code == 429 or e.code >= 500:
                time.sleep(int(e.headers.get("Retry-After") or 10) + 2 * i); continue
            raise
        except (urllib.error.URLError, TimeoutError, ConnectionError, ValueError, KeyError):
            time.sleep(min(10 + 10 * i, 90))
    raise RuntimeError(f"Index One {name} failed after {tries} tries")

def fetch(operation, parameters, max_rows=200000):
    """运行一个取数操作，返回 (行列表, 消息)。"""
    r = call("run_workflow", {"operations": json.dumps([{"id": "x", "operation": operation, "parameters": parameters}])})
    res = r["results"]["x"]
    if res["state"].get("error"):
        raise RuntimeError(res.get("message"))
    n = res["output"]["row_count"]
    if n == 0:
        return [], res["message"]
    s = call("inspect_run", {"op_id": "x", "view": "sample", "sample_rows": max_rows, "limit": max_rows, "run_id": r["run_id"]})
    rows = s["sample"]
    if len(rows) != n:
        raise RuntimeError(f"{operation}: got {len(rows)} of {n} rows (truncated={s.get('sample_truncated')})")
    return rows, res["message"]
