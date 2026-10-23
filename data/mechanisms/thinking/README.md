# Inputs of the thinking analysis (mechanism 4 of 4)

`finagent.mechanisms.thinking` has no input files of its own: nothing was copied into this folder. It reads
only the two shared session corpora, which were copied once for all four mechanism analyses:

| folder in this repository | source in the research workspace (relative to it) | files read |
|---|---|---|
| `data/mechanisms/sessions/newsagent/` | `results/newsagent_20261011/raw/sessions/` | 2,000 |
| `data/mechanisms/sessions/q3news_s1/` | `results/q3news_20261012/S1/sessions/` | 2,000 |

Files read: the plain `<TICKER>_<date>/FULL_<k>.json.gz` and `NO_NEWS_<k>.json.gz` sessions (k = 0..3) of both
corpora; the `FULL_T06_*` files in the same folders are not used. Each of the 4,000 files was checked to be
byte-identical to its workspace source.

sha256 of the list of those 4,000 files (one `<sha256>  <path>` line per file, in the order the analysis reads
them: corpus, then ticker-day folder, then file name, both sorted; paths relative to the repository root):

    3ca2549837af836059e58d988a27a561d767fe8d65026986346c2f49df990968

To recompute it:

    python -c "import hashlib; from finagent import config; from finagent.mechanisms import thinking as M; print(hashlib.sha256(''.join(f'{hashlib.sha256(f.read_bytes()).hexdigest()}  {config.rel(f)}\n' for _, f, _, _ in M.session_files()).encode()).hexdigest())"

Hand-check judgments and verbatim example excerpts are constants in `src/finagent/mechanisms/thinking_text.py`.
The code checks every excerpt against its session file.
