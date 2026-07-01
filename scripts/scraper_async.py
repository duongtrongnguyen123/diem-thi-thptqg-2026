#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Async scraper for VietnamNet điểm thi THPT 2026.
Drop-in replacement — same CLI args, same CSV/checkpoint format.
Uses aiohttp + asyncio: true concurrent I/O, no GIL bottleneck.
Regex parsing instead of BeautifulSoup: ~10x faster per page.
"""
import argparse, asyncio, csv, json, os, random, re, sys
import aiohttp

YEAR = 2026
URL_TMPL = ("https://vietnamnet.vn/giao-duc/diem-thi/"
            "tra-cuu-diem-thi-tot-nghiep-thpt/{year}/{sbd}.html")

CANON_COLS = [
    "sbd", "province_code", "province_name",
    "toan", "ngu_van", "ngoai_ngu",
    "vat_li", "hoa_hoc", "sinh_hoc",
    "lich_su", "dia_li", "gdcd",
    "tin_hoc", "cong_nghe", "extra",
]

SUBJECT_MAP = {
    "toán": "toan",
    "ngữ văn": "ngu_van", "văn": "ngu_van",
    "ngoại ngữ": "ngoai_ngu", "tiếng anh": "ngoai_ngu",
    "vật lí": "vat_li", "vật lý": "vat_li", "lí": "vat_li", "lý": "vat_li",
    "hóa học": "hoa_hoc", "hoá học": "hoa_hoc", "hóa": "hoa_hoc", "hoá": "hoa_hoc",
    "sinh học": "sinh_hoc", "sinh": "sinh_hoc",
    "lịch sử": "lich_su", "sử": "lich_su",
    "địa lí": "dia_li", "địa lý": "dia_li", "địa": "dia_li",
    "giáo dục công dân": "gdcd", "gdcd": "gdcd",
    "tin học": "tin_hoc", "tin": "tin_hoc",
    "công nghệ": "cong_nghe",
}

PROVINCE_NAMES = {
    "01": "Hà Nội",      "04": "Cao Bằng",    "08": "Tuyên Quang",
    "11": "Điện Biên",   "12": "Lai Châu",     "14": "Sơn La",
    "15": "Lào Cai",     "19": "Thái Nguyên",  "20": "Lạng Sơn",
    "22": "Quảng Ninh",  "24": "Bắc Ninh",     "25": "Phú Thọ",
    "31": "Hải Phòng",   "33": "Hưng Yên",     "37": "Ninh Bình",
    "38": "Thanh Hóa",   "40": "Nghệ An",      "42": "Hà Tĩnh",
    "44": "Quảng Trị",   "46": "Huế",           "48": "Đà Nẵng",
    "51": "Quảng Ngãi",  "52": "Gia Lai",      "56": "Khánh Hòa",
    "66": "Đắk Lắk",    "68": "Lâm Đồng",     "75": "Đồng Nai",
    "79": "Hồ Chí Minh","80": "Tây Ninh",     "82": "Đồng Tháp",
    "86": "Vĩnh Long",   "91": "An Giang",     "92": "Cần Thơ",
    "96": "Cà Mau",
}

HEADERS = {
    "User-Agent": ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                   "AppleWebKit/537.36 (KHTML, like Gecko) "
                   "Chrome/124.0 Safari/537.36"),
    "Accept-Language": "vi,en;q=0.9",
}

# --- Fast regex HTML parser (replaces BeautifulSoup) ---
_TAG = re.compile(r'<[^>]+>', re.DOTALL)
_WS  = re.compile(r'\s+')
_TBL = re.compile(r'<table[^>]*>.*?</table>', re.DOTALL | re.IGNORECASE)
_TR  = re.compile(r'<tr[^>]*>(.*?)</tr>',     re.DOTALL | re.IGNORECASE)
_TD  = re.compile(r'<t[dh][^>]*>(.*?)</t[dh]>', re.DOTALL | re.IGNORECASE)

def _txt(h):
    return _WS.sub(' ', _TAG.sub('', h)).strip()

def parse_scores(html, sbd):
    sbd = str(sbd)
    tbl = None
    for m in _TBL.finditer(html):
        t = m.group(0)
        if 'Môn' in t and 'Điểm' in t:
            tbl = t
            break
    if tbl is None:
        return None

    data = {c: "" for c in CANON_COLS}
    data["sbd"] = sbd
    data["province_code"] = sbd[:2]
    data["province_name"] = PROVINCE_NAMES.get(sbd[:2], "")
    found = False
    extras = []

    for tr in _TR.finditer(tbl):
        tds = _TD.findall(tr.group(1))
        if len(tds) < 2:
            continue
        label = _txt(tds[0])
        score = _txt(tds[1])
        if label.lower() == "môn":
            continue
        k = SUBJECT_MAP.get(label.lower())
        if k:
            data[k] = score
            found = True
        elif label:
            extras.append(f"{label}={score}")
            found = True

    if not found:
        return None
    if extras:
        data["extra"] = "; ".join(extras)
    return data


# --- Async rate limiter ---
class RateLimiter:
    def __init__(self, rps):
        self._iv = 1.0 / rps if rps > 0 else 0.0
        self._nxt = 0.0
        self._lock = asyncio.Lock()

    async def wait(self):
        if not self._iv:
            return
        async with self._lock:
            loop = asyncio.get_event_loop()
            now = loop.time()
            w = self._nxt - now
            if w > 0:
                await asyncio.sleep(w)
            self._nxt = max(self._nxt, loop.time()) + self._iv


# --- Single-SBD fetch ---
async def fetch_one(session, sem, rl, sbd, retries, timeout):
    url = URL_TMPL.format(year=YEAR, sbd=sbd)
    to  = aiohttp.ClientTimeout(total=timeout)
    bo  = 1.5
    for _ in range(retries + 1):
        await rl.wait()
        try:
            async with sem:
                async with session.get(url, headers=HEADERS, timeout=to) as r:
                    if r.status == 200:
                        html = await r.text(errors='replace')
                        data = parse_scores(html, sbd)
                        return ("hit", data) if data else ("miss", None)
                    if r.status in (404, 410):
                        return ("miss", None)
        except Exception:
            pass
        await asyncio.sleep(bo + random.random())
        bo *= 2
    return ("error", None)


# --- Sliding-window province scraper ---
async def scrape_prefix(pfx, session, sem, rl, writer, wlock, seen, args, stats):
    pfx = f"{int(pfx):02d}"
    WINDOW = args.workers
    seq = args.seq_start
    head = args.seq_start
    cmiss = 0
    hits = 0
    pending = {}   # seq -> Task
    tseq   = {}    # id(task) -> seq
    buf    = {}    # seq -> (status, data)

    def spawn(s):
        sbd = f"{pfx}{s:06d}"
        async def _f():
            if sbd in seen:
                return ("seen", None)
            return await fetch_one(session, sem, rl, sbd, args.retries, args.timeout)
        t = asyncio.create_task(_f())
        pending[s] = t
        tseq[id(t)] = s

    # Fill initial window
    while seq <= args.seq_end and len(pending) < WINDOW:
        spawn(seq)
        seq += 1

    while pending:
        done, _ = await asyncio.wait(
            list(pending.values()), return_when=asyncio.FIRST_COMPLETED
        )
        for task in done:
            s = tseq.pop(id(task))
            del pending[s]
            try:
                buf[s] = task.result()
            except Exception:
                buf[s] = ("error", None)
            # keep window full
            if seq <= args.seq_end:
                spawn(seq)
                seq += 1

        # Drain ordered buffer
        stop = False
        while head in buf:
            status, data = buf.pop(head)
            head += 1
            if status == "hit" and data:
                cmiss = 0
                hits += 1
                async with wlock:
                    writer.writerow([data[c] for c in CANON_COLS])
                    stats["hits"] += 1
                    if stats["hits"] % 500 == 0:
                        stats["_fh"].flush()
            elif status == "miss":
                cmiss += 1
                stats["misses"] += 1
            elif status == "seen":
                stats["misses"] += 1
            else:
                stats["errors"] += 1

            if cmiss >= args.max_miss:
                stop = True
                break

        sys.stderr.write(
            f"\r[{pfx}] seq~{head:>6} | hits={hits} "
            f"total={stats['hits']} miss_streak={cmiss} "
            f"errors={stats['errors']}   "
        )
        sys.stderr.flush()

        if stop:
            for t in pending.values():
                t.cancel()
            await asyncio.gather(*list(pending.values()), return_exceptions=True)
            pending.clear()
            break

    sys.stderr.write(f"\n[{pfx}] done: {hits}\n")
    return hits


# --- Checkpoint / seen helpers ---
def load_checkpoint(path):
    if path and os.path.exists(path):
        try:
            with open(path, encoding='utf-8') as f:
                return set(json.load(f).get("done_prefixes", []))
        except Exception:
            pass
    return set()

def save_checkpoint(path, done):
    if not path:
        return
    tmp = path + ".tmp"
    with open(tmp, 'w', encoding='utf-8') as f:
        json.dump({"done_prefixes": sorted(done)}, f)
    os.replace(tmp, path)

def load_seen(path):
    seen = set()
    if path and os.path.exists(path):
        try:
            with open(path, encoding='utf-8', newline='') as f:
                for row in csv.DictReader(f):
                    if row.get("sbd"):
                        seen.add(row["sbd"])
        except Exception:
            pass
    return seen


# --- Main ---
async def run(args):
    ckpt_path = args.checkpoint or (args.out + ".checkpoint.json")
    done_pfx  = load_checkpoint(ckpt_path)
    seen      = load_seen(args.out)
    if seen:
        sys.stderr.write(f"Resume: {len(seen)} SBDs already in {args.out}\n")

    prefixes = [f"{int(p):02d}" for p in args.prefixes.split(",") if p.strip()]

    new_file = not os.path.exists(args.out) or os.path.getsize(args.out) == 0
    fh = open(args.out, "a", encoding="utf-8", newline="")
    writer = csv.writer(fh)
    if new_file:
        writer.writerow(CANON_COLS)
        fh.flush()

    stats = {"hits": 0, "misses": 0, "errors": 0, "_fh": fh}
    wlock = asyncio.Lock()
    sem   = asyncio.Semaphore(args.workers)
    rl    = RateLimiter(args.rate)

    conn = aiohttp.TCPConnector(limit=args.workers + 20, ttl_dns_cache=300)
    try:
        async with aiohttp.ClientSession(connector=conn) as session:
            for pfx in prefixes:
                if pfx in done_pfx:
                    sys.stderr.write(f"[{pfx}] already done, skipping.\n")
                    continue
                await scrape_prefix(pfx, session, sem, rl, writer, wlock,
                                    seen, args, stats)
                done_pfx.add(pfx)
                save_checkpoint(ckpt_path, done_pfx)
    except asyncio.CancelledError:
        sys.stderr.write("\nCancelled.\n")
    finally:
        fh.flush()
        fh.close()

    sys.stderr.write(
        f"\nDone: {stats['hits']} hits, {stats['misses']} misses, "
        f"{stats['errors']} errors\n"
    )


def main():
    ap = argparse.ArgumentParser(description="Async điểm thi THPT 2026 scraper")
    ap.add_argument("--out",        default="diemthi_2026.csv")
    ap.add_argument("--prefixes",   default="")
    ap.add_argument("--rate",       type=float, default=0,
                    help="req/s per process (0 = unlimited)")
    ap.add_argument("--workers",    type=int, default=200,
                    help="concurrent async coroutines")
    ap.add_argument("--retries",    type=int, default=3)
    ap.add_argument("--timeout",    type=float, default=15)
    ap.add_argument("--seq-start",  type=int, default=1)
    ap.add_argument("--seq-end",    type=int, default=999999)
    ap.add_argument("--max-miss",   type=int, default=1000)
    ap.add_argument("--flush-every",type=int, default=50)   # kept for compat
    ap.add_argument("--checkpoint", default="")
    args = ap.parse_args()
    asyncio.run(run(args))


if __name__ == "__main__":
    main()
