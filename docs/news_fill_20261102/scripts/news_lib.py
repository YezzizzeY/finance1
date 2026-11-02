"""News helpers for the RCF event set (PLAN_zh.md section 4): company-name / ticker relevance filter, regex masking
of price-move narration, headline Jaccard for the first-report filter, and Finnhub coverage intervals.

Coverage (needed because Finnhub returns at most ~250 items per call, newest first):
  * existing DJIA-30 pull (results/_panel/dow30/news, repro/fetch_dow30_news.py): monthly windows [1st, 1st of next
    month]; a window with >= 150 items is treated as truncated and covered only from its 230th-newest item; the API
    floor at that pull was 2025-09-29, so coverage starts 2025-09-30 00:00 UTC;
  * new pull (fetch_news.py state): per call [a 00:00 UTC + 5 h, b 24:00 UTC] if n < 150, else [oldest item, b 24:00 UTC];
    the floor of every new call is 2025-10-15 00:00 UTC (the free tier returned nothing earlier than 2025-10-15 00:03 UTC).
"""
from __future__ import annotations
import datetime as dt
import json
import re
from pathlib import Path

U = dt.UTC
TRUNC_N = 150

# ----------------------------------------------------------------------------------------------- company names
# Proper-noun aliases, matched case-sensitively with word boundaries (headlines are title case; summaries prose).
NAMES = {
    "AAPL": ["Apple"], "AMGN": ["Amgen"], "AMZN": ["Amazon"], "AXP": ["American Express", "Amex", "AmEx"],
    "BA": ["Boeing"], "CAT": ["Caterpillar"], "CRM": ["Salesforce"], "CSCO": ["Cisco"], "CVX": ["Chevron"],
    "DIS": ["Disney"], "GS": ["Goldman Sachs", "Goldman"], "HD": ["Home Depot"], "HON": ["Honeywell"], "IBM": ["IBM"],
    "JNJ": ["Johnson & Johnson", "Johnson &amp; Johnson", "Johnson and Johnson", "J&J", "J&amp;J"],
    "JPM": ["JPMorgan", "JP Morgan", "J.P. Morgan", "JPMorganChase"], "KO": ["Coca-Cola", "Coca Cola", "Coke"],
    "MCD": ["McDonald's", "McDonald’s", "McDonalds"], "MMM": ["3M"], "MRK": ["Merck"], "MSFT": ["Microsoft"],
    "NKE": ["Nike"], "NVDA": ["Nvidia", "NVIDIA"], "PG": ["Procter & Gamble", "Procter &amp; Gamble", "Procter and Gamble", "P&G", "P&amp;G"],
    "SHW": ["Sherwin-Williams", "Sherwin Williams"], "TRV": ["Travelers Companies", "Travelers Cos", "Travelers"],
    "UNH": ["UnitedHealth", "United Health", "UnitedHealthcare"], "V": ["Visa"], "VZ": ["Verizon"],
    "WMT": ["Walmart", "Wal-Mart"],
    "ABNB": ["Airbnb"], "ACN": ["Accenture"], "AJG": ["Arthur J. Gallagher", "Gallagher"], "ALB": ["Albemarle"],
    "AME": ["AMETEK", "Ametek"], "AMT": ["American Tower"], "AVGO": ["Broadcom"], "BAC": ["Bank of America", "BofA"],
    "CB": ["Chubb"], "CI": ["Cigna"], "CIEN": ["Ciena"], "COR": ["Cencora"], "CRH": ["CRH"], "CRWD": ["CrowdStrike"],
    "CSGP": ["CoStar"], "DG": ["Dollar General"], "DLR": ["Digital Realty"], "DVN": ["Devon Energy", "Devon"],
    "EA": ["Electronic Arts"], "ECL": ["Ecolab"], "ED": ["Consolidated Edison", "Con Edison", "ConEd", "Con Ed"],
    "ELV": ["Elevance"], "FERG": ["Ferguson"], "FITB": ["Fifth Third"], "FIX": ["Comfort Systems"],
    "FSLR": ["First Solar"], "GLW": ["Corning"], "GM": ["General Motors", "GM"], "GWW": ["Grainger"],
    "HAL": ["Halliburton"], "HCA": ["HCA"], "HOOD": ["Robinhood"], "HWM": ["Howmet"], "IDXX": ["IDEXX", "Idexx"],
    "LEN": ["Lennar"], "LHX": ["L3Harris", "L3 Harris"], "LMT": ["Lockheed Martin", "Lockheed"],
    "LYB": ["LyondellBasell", "Lyondell"], "MA": ["Mastercard", "MasterCard"], "MCHP": ["Microchip"], "MSCI": ["MSCI"],
    "NEE": ["NextEra"], "NFLX": ["Netflix"], "NRG": ["NRG"], "O": ["Realty Income"], "ORCL": ["Oracle"],
    "PANW": ["Palo Alto Networks"], "PLTR": ["Palantir"], "PNC": ["PNC"], "RDDT": ["Reddit"],
    "ROK": ["Rockwell Automation", "Rockwell"], "ROST": ["Ross Stores"], "RSG": ["Republic Services"],
    "SCHW": ["Charles Schwab", "Schwab"], "SRE": ["Sempra"], "STX": ["Seagate"], "TFC": ["Truist"],
    "UAL": ["United Airlines"], "UBER": ["Uber"], "VLO": ["Valero"], "VRTX": ["Vertex Pharmaceuticals", "Vertex"],
    "VST": ["Vistra"], "WAT": ["Waters Corp", "Waters Corporation"], "WELL": ["Welltower"],
    "WM": ["Waste Management", "WM"], "WMB": ["Williams Companies", "Williams Cos"],
}
# bare upper-case tickers that are ordinary words or too short are matched only in ticker context ($X, (X), NYSE:X)
BARE_OK_MIN = 3
WORDLIKE = {"CAT", "DIS", "HON", "FIX", "COR", "WELL", "HOOD", "ALB", "AME", "LEN", "HAL", "ROK", "WAT", "CB", "CI",
            "ED", "GM", "MA", "PG", "BA", "HD", "KO", "GS", "V", "O", "VZ", "WM", "DG", "EA", "AMT", "CRH", "MSCI"}


def _rx_name(n: str) -> str:
    return r"(?<![A-Za-z0-9])" + re.escape(n) + r"(?![A-Za-z0-9])"


# name patterns that need context exclusions (regex, case-sensitive)
NAME_RX = {
    "MMM": [r"(?<![$\d.,A-Za-z])3M(?![A-Za-z0-9])(?! (?:users|subscribers|customers|views|shares|downloads|people|units|barrels|members|jobs|homes|vehicles|cars|devices|accounts|tons|acres|visitors|in|of|to|for|from)\b)"],
    "MSCI": [r"(?<![A-Za-z0-9])MSCI(?![A-Za-z0-9])(?! (?:World|EAFE|Emerging|EM|ACWI|All|AC|USA|US|U\.S\.|Europe|China|Japan|India|Asia|Index|index|indices|indexes|Indices|Indexes|Global|Korea|Taiwan|Brazil|Frontier|Country|Developed|ESG|Minimum|Min|Value|Growth|Momentum|Quality|benchmark|rebalanc))"],
    "RDDT": [r"(?<!on )(?<!On )(?<!via )Reddit(?![A-Za-z0-9])(?! (?:sentiment|users|posts|threads|forums?|discussions?|chatter|thread|post|user)\b)(?!'s r/)"],
    "V": [r"(?<!H-1B )(?<!H1-B )(?<!H-2B )(?<!Golden )(?<!Gold )(?<!Student )(?<!Work )(?<![A-Za-z0-9-])Visa(?![A-Za-z0-9])(?! (?:Fee|Fees|Program|Programs|Rules|Holders|Applicants|Applications|Policy|Policies|Ban|Lottery|Restrictions|Overhaul|Crackdown|Waiver|Bond|Bonds|Requirements|Interview|Interviews|Processing|Pause|Freeze|Changes)\b)"],
    "VRTX": [r"(?<![A-Za-z0-9])Vertex(?![A-Za-z0-9])(?! (?:AI|Inc\b(?! \(VRTX)|Energy|Aerospace|Ventures|Holdings)\b)"],
    "MRK": [r"(?<![A-Za-z0-9])Merck(?![A-Za-z0-9])(?! KGaA)(?! Group)"],
    "SCHW": [r"(?<![A-Za-z0-9])(?:Charles )?Schwab(?![A-Za-z0-9])(?! (?:U\.S\.|US|International|Fundamental|Dividend|Emerging|ETF|ETFs|Total|Strategic|Short-Term|Intermediate|Long-Term|1000|Broad|Asset Management|Center|Trading Activity|Ultra|High Yield|Municipal|Crypto Thematic|Ariel|Mortgage|Treasury)(?![A-Za-z0-9]))(?!'s ETF)"],
}
# sell-side brands of banks in the set: analyst attributions ('upgraded by Goldman Sachs') are not news about the bank
ANALYST = {"GS": r"Goldman Sachs|Goldman", "JPM": r"J\.P\. Morgan|JPMorgan|JP Morgan", "BAC": r"BofA|Bank of America",
           "TFC": r"Truist"}
_ANALYST_VERBS = (r"analysts?|analyst team|strategists?|economists?|research|securities|global research|upgrad\w*|downgrad\w*|"
                  r"rais\w*|lift\w*|cut\w*|lower\w*|boost\w*|trim\w*|initiat\w*|maintain\w*|reiterat\w*|sees?|says?|said|"
                  r"expects?|predicts?|forecasts?|recommends?|names?|adds?|picks?|likes?|reaffirm\w*|resum\w*|starts?|keeps?|"
                  r"sets?|price targets?|pt|rates?|rated|note|team|survey|estimates?|calls?|warns?|thinks?|is (?:bullish|bearish)|"
                  r"(?:has|have) (?:a|an)|top picks?|conviction")


def strip_analyst(tk: str, s: str) -> str:
    if tk not in ANALYST or not s:
        return s
    nm = ANALYST[tk]
    s = re.sub(rf"(?i:by|from|at|per|with|says|said|according to|via|told|note from|analysts at|analyst at)\s+(?:analysts? at\s+)?(?:{nm})(?:\s+(?i:Securities|Research|Global Research|Global Investment Research|Investment Research))?", " ", s)
    s = re.sub(rf"(?:{nm})(?:\s+(?i:Securities|Research|Global Research|Global Investment Research|Investment Research))?(?:'s|\u2019s)?\s+(?i:{_ANALYST_VERBS})\b", " ", s)
    return s


def relevant(tk: str, rx: re.Pattern, *texts: str) -> bool:
    return any(t and rx.search(strip_analyst(tk, t)) for t in texts)


def relevance_rx(tk: str) -> re.Pattern:
    parts = NAME_RX.get(tk, []) + [_rx_name(n) for n in NAMES[tk] if tk not in NAME_RX or n not in ("3M", "MSCI", "Reddit", "Visa", "Vertex", "Merck", "Schwab", "Charles Schwab")]
    parts.append(r"(?:\$|\(|(?:NYSE|NASDAQ|Nasdaq|NasdaqGS|NYSEARCA|BATS)\s?:\s?)" + re.escape(tk) + r"(?![A-Za-z0-9])")
    if len(tk) >= BARE_OK_MIN and tk not in WORDLIKE:
        parts.append(r"(?<![A-Za-z0-9$])" + re.escape(tk) + r"(?![A-Za-z0-9])")
    return re.compile("|".join(parts))


# ----------------------------------------------------------------------------------------------- price-move masking
MASK = "[price move]"
STRONG = (r"soar(?:s|ed|ing)?|surg(?:e|es|ed|ing)|jump(?:s|ed|ing)?|plung(?:e|es|ed|ing)|plummet(?:s|ed|ing)?|"
          r"tumbl(?:e|es|ed|ing)|slump(?:s|ed|ing)?|sink(?:s|ing)?|sank|sunk|slid(?:e|es|ing)?|rall(?:y|ies|ied|ying)|"
          r"skyrocket(?:s|ed|ing)?|rocket(?:s|ed|ing)?|spik(?:e|es|ed|ing)|tank(?:s|ed|ing)?|crater(?:s|ed|ing)?|"
          r"nosediv(?:e|es|ed|ing)|dives?|dived|dove|crash(?:es|ed|ing)?|rebound(?:s|ed|ing)?|pops?|popped|popping|"
          r"sell[- ]?off|sold off|sells off|whipsaw(?:s|ed)?|zoom(?:s|ed)?|lurch(?:es|ed)?|skid(?:s|ded)?|"
          r"hit(?:s)? (?:a )?(?:new )?(?:record|all-time) (?:high|low)s?|(?:nearly |more than |almost )?doubl(?:e|es|ed|ing)(?! down)|"
          r"(?:nearly |more than |almost )?tripl(?:e|es|ed|ing)|halv(?:e|es|ed|ing)|moving (?:up|down|higher|lower)|"
          r"(?:is|are|was|were) (?:soaring|sinking|plunging|surging|tumbling|sliding|rallying|climbing|falling|rising|jumping|dropping)")
CORE = (r"ris(?:e|es|ing)|rose|risen|gain(?:s|ed|ing)?|climb(?:s|ed|ing)?|fall(?:s|ing|en)?|fell|drop(?:s|ped|ping)?|"
        r"declin(?:e|es|ed|ing)|dip(?:s|ped|ping)?|slip(?:s|ped|ping)?|advanc(?:e|es|ed|ing)|retreat(?:s|ed|ing)?|"
        r"edg(?:e|es|ed|ing) (?:up|down|higher|lower)|trad(?:e|es|ed|ing) (?:up|down|higher|lower)|"
        r"(?:move[sd]?|end(?:s|ed)?|clos(?:e|es|ed)|finish(?:es|ed)?|open(?:s|ed)?) (?:up|down|higher|lower)|"
        r"up|down|higher|lower")
WEAK = CORE + r"|add(?:s|ed)?|shed(?:s|ding)?|los(?:e|es|ing)|lost|outperform(?:s|ed|ing)?|underperform(?:s|ed|ing)?"
NUM = (r"(?:\s+(?:by|as much as|about|nearly|almost|roughly|around|more than|over|some|another|an?|just|only)){0,2}"
       r"\s*[-+−]?\$?\d+(?:[.,]\d+)?\s?(?:%|percent|per cent|points?|pts|bps)")
TRAIL = (r"(?:\s+(?:in|during|on|at|after)\s+(?:the\s+)?(?:early|late|extended|after-hours|after hours|afterhours|"
         r"pre-?market|overnight|thin|heavy|midday|morning|afternoon|aftermarket|post-?market|regular)"
         r"(?:\s+(?:trading|trade|session|deals|action|hours))?|\s+(?:after hours|after-hours|after the bell|before the bell|"
         r"premarket|pre-market|overnight|late|early))?")
STOCKSUBJ = r"(?:shares|share price|stock price|stock|stocks|ADRs?)"
FILL = (r"(?:\s+(?:of\s+the\s+company|of\s+[A-Z][\w.&'-]*|in\s+\w+|have|has|had|were|was|are|is|been|also|sharply|"
        r"slightly|modestly|nearly|about|briefly|further|initially|then|just|now|still|again|more|even|all|reportedly|"
        r"already|quickly|steeply|substantially|significantly|dramatically|immediately|today|currently|recently)){0,3}")
MARKETSUBJ = (r"(?:Dow(?: Jones)?(?: Industrial Average)?|S&P(?: 500)?|S&amp;P(?: 500)?|Nasdaq(?: Composite| 100)?|"
              r"Russell 2000|(?i:indexes|indices|index|futures|Wall Street|stock market|the market|markets))")
FUND = (r"(?:revenue|revenues|sales|profit|profits|earnings|EPS|income|margin|margins|yield|yields|dividend|dividends|"
        r"spending|growth|guidance|deliveries|subscribers|volume|bookings|orders|backlog|cost|costs|expenses|prices|"
        r"rate|rates|payout|demand|traffic|comps|users|output|production|shipments|assets|deposits|loans|premiums|"
        r"capex|inflation|unemployment|jobs|wages|outlook|forecast|estimate|estimates|target|targets|stake|holdings|"
        r"position|ratio|value|cash|debt|NII|AUM|ARR|GMV|bookings|members|customers|headcount|workforce|staff|count|"
        r"interest|imports|exports|tariffs?|shipments|volumes|units|transactions|purchase|buyback|investment)")
_STOP = r"(?:but|while|yet|though|although|whereas|shares|stock|stocks)"
_FUND_RX = re.compile(rf"\b{FUND}\b(?:[\s,]+(?!{_STOP}\b)[^\s;:!?]+){{0,4}}[\s,]*$", re.I)       # noun shortly before
_FUND_AFTER = re.compile(rf"^\s+(?:in|of|for)\s+(?:[\w'-]+\s+){{0,2}}{FUND}\b", re.I)               # '... surge in revenue'
MOVE_NOUN = (r"(?:\b(?:a|an)\s+)?[-+−]?\d+(?:\.\d+)?\s?(?:%|percent)\s+(?:(?:one-day|single-day|intraday|daily|"
             r"weekly|stock|share|price|after-hours|premarket|pre-market)\s+){0,2}"
             r"(?:gain|loss|drop|decline|jump|surge|plunge|rally|move|slide|selloff|sell-off|tumble|pop|climb|swing|"
             r"rise|fall|advance|rebound|spike|slump|dip)s?\b")
LEVEL = (r"(?:\b(?:hits?|reach(?:es|ed)?|touch(?:es|ed)?|sets?|notch(?:es|ed)?|smash(?:es|ed)?)\s+(?:a\s+|its\s+)?)?"
         r"(?:\bnew\s+|\bfresh\s+)?\b(?:record|all-time|all time|52-week|\d+-week|\d+-month|multi-year|multiyear|\d+-year)"
         r"\s+(?:closing\s+|intraday\s+|stock\s+|share\s+)?(?:highs?|lows?)\b")
PRICE_LEVEL = (r"\b(?:closed|closes|close|ended|ends|finished|opened|opens|trading|trades|traded|trade|sits|sat|hovering|"
               r"hovers|changing hands)\s+(?:at|around|near|above|below|to)\s+(?:about\s+|around\s+|roughly\s+)?\$\d+(?:[.,]\d+)?")


def mask_rx(tk: str) -> list[re.Pattern]:
    names = "|".join(re.escape(n) for n in sorted(set(NAMES[tk] + [tk]), key=len, reverse=True))
    NS = rf"(?:(?<![A-Za-z0-9])(?:{names})(?:'s|’s)?(?:\s+\((?:[A-Za-z]+:\s?)?[A-Z.]+\))?(?:\s+Inc\.?|\s+Corp\.?|\s+Co\.?)?)"
    I = re.I
    return [
        re.compile(rf"(?:[-+\u2212]?\d+(?:\.\d+)?\s?%\s+)?\b{STOCKSUBJ}{FILL}\s+(?:{STRONG}|{WEAK})\b(?:{NUM})?{TRAIL}", I),               # 0 stock/shares + move
        re.compile(rf"(?P<keep>{NS})\s+(?i:{STRONG})\b(?:{NUM})?{TRAIL}"),                                       # 1 name + strong verb
        re.compile(rf"(?P<keep>{NS})\s+(?i:{WEAK})\b{NUM}{TRAIL}"),                                                # 2 name + verb + number
        re.compile(rf"(?P<keep>{NS})\s+(?i:{CORE})\b(?=\s+(?i:after|on|as|in|following|despite|amid|ahead|post|premarket|pre-market|overnight|today|since|toward|towards)\b)"),  # 3
        re.compile(rf"\b{MARKETSUBJ}{FILL}\s+(?i:{STRONG}|{CORE})\b(?:{NUM})?{TRAIL}"),                   # 4 index / market
        re.compile(rf"\b(?:{STRONG}|{CORE})\b{NUM}{TRAIL}", I),                                             # 5 verb + number (FUND guard)
        re.compile(MOVE_NOUN, I),                                                                           # 6 'a 12% drop'
        re.compile(LEVEL, I),                                                                               # 7 record / 52-week high
        re.compile(PRICE_LEVEL, I),                                                                         # 8 'closed at $76.04'
    ]


def mask_text(s: str, pats: list[re.Pattern]) -> tuple[str, int]:
    """Replace price-move narration by MASK. Returns (masked text, number of replacements). The generic
    'verb + number' (5) and 'number + move noun' (6) rules are skipped when a fundamental noun (revenue, EPS, ...)
    precedes them within 4 words (not across 'but', 'while', 'shares', ...) or follows as 'in/of <noun>'."""
    if not s:
        return s, 0
    n = 0
    for i, p in enumerate(pats):
        out, last = [], 0
        for m in p.finditer(s):
            if MASK in m.group(0) or m.start() < last:
                continue
            if i in (5, 6) and (_FUND_RX.search(s[max(0, m.start() - 60):m.start()]) or _FUND_AFTER.search(s[m.end():m.end() + 40])):
                continue
            keep = m.groupdict().get("keep")
            out.append(s[last:m.start()]); out.append((keep + " " if keep else "") + MASK); last = m.end(); n += 1
        out.append(s[last:]); s = "".join(out)
    s = re.sub(r"\[price move\](?:[\s,;]*\[price move\])+", MASK, s)
    return re.sub(r"[ \t]{2,}", " ", s).strip(), n


# ----------------------------------------------------------------------------------------------- first-report filter
_TOK = re.compile(r"[a-z0-9]+")


def tokset(h: str) -> frozenset:
    return frozenset(_TOK.findall((h or "").lower().replace("&amp;", "&")))


def jaccard(a: frozenset, b: frozenset) -> float:
    if not a or not b:
        return 0.0
    return len(a & b) / len(a | b)


# ----------------------------------------------------------------------------------------------- coverage
def _merge(iv):
    iv = sorted(iv); out = []
    for lo, hi in iv:
        if out and lo <= out[-1][1]:
            out[-1] = (out[-1][0], max(out[-1][1], hi))
        else:
            out.append((lo, hi))
    return out


def day0(s: str) -> int:
    return int(dt.datetime.fromisoformat(s).replace(tzinfo=U).timestamp())


EXISTING_FLOOR = day0("2025-09-30")
NEW_FLOOR = day0("2025-10-15")          # earliest item any call of the new pull returned: 2025-10-15 00:03 UTC
NEW_FLOOR_HELDOUT = NEW_FLOOR


def existing_coverage(items: list[dict]) -> list[tuple[int, int]]:
    months = [(2025, m) for m in range(3, 13)] + [(2026, m) for m in range(1, 4)]
    iv = []
    for y, m in months:
        a = dt.date(y, m, 1); b = dt.date(y + (m == 12), m % 12 + 1, 1)
        lo, hi = day0(a.isoformat()), day0(b.isoformat()) + 86400
        S = sorted((x["datetime"] for x in items if x["datetime"] and lo <= x["datetime"] < hi), reverse=True)
        if len(S) >= TRUNC_N:
            lo = S[min(229, len(S) - 1)]
        lo = max(lo + (0 if len(S) >= TRUNC_N else 5 * 3600), EXISTING_FLOOR)
        if hi > lo:
            iv.append((lo, hi))
    return _merge(iv)


def new_coverage(calls: list[dict], floor: int) -> list[tuple[int, int]]:
    iv = []
    for c in calls:
        if c.get("n") is None:
            continue
        lo, hi = day0(c["a"]) + 5 * 3600, day0(c["b"]) + 86400
        if c["n"] >= TRUNC_N:
            lo = c["min"]
        lo = max(lo, floor)
        if hi > lo:
            iv.append((lo, hi))
    return _merge(iv)


def covered(iv: list[tuple[int, int]], a: int, b: int) -> bool:
    return any(lo <= a and b <= hi for lo, hi in iv)
