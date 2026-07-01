#!/bin/bash
# Merge all worker CSVs, dedup by SBD, split into per-province files.
# Run from repo root: bash scripts/build_dataset.sh <path-to-diemthi2026-dir>
set -e
SRC="${1:-../diemthi2026}"
DATA="data"
mkdir -p "$DATA"

echo "=== Merging CSVs from $SRC ==="
MERGED="$DATA/diem_thi_thptqg_2026_all.csv"

# Write header once
head -1 "$SRC/diemthi_w2.csv" > "$MERGED"

# Append all worker CSVs (skip header)
for f in \
  "$SRC/diemthi_w2.csv" "$SRC/diemthi_w3.csv" "$SRC/diemthi_w4.csv" \
  "$SRC/r1.csv" "$SRC/r2.csv" "$SRC/r3.csv"; do
  [ -f "$f" ] && tail -n +2 "$f" >> "$MERGED" && echo "  + $f"
done

BEFORE=$(wc -l < "$MERGED")
echo "Rows before dedup: $((BEFORE - 1))"

# Dedup by SBD (column 1), keep first occurrence, preserve header
python3 - "$MERGED" <<'PYEOF'
import csv, sys
path = sys.argv[1]
tmp  = path + ".tmp"
seen = set()
with open(path, newline="", encoding="utf-8") as fin, \
     open(tmp,  "w", newline="", encoding="utf-8") as fout:
    reader = csv.reader(fin)
    writer = csv.writer(fout)
    for i, row in enumerate(reader):
        if i == 0:
            writer.writerow(row)
            continue
        sbd = row[0] if row else ""
        if sbd and sbd not in seen:
            seen.add(sbd)
            writer.writerow(row)
import os; os.replace(tmp, path)
print(f"Unique students: {len(seen)}")
PYEOF

echo "=== Sorting by SBD ==="
python3 - "$MERGED" <<'PYEOF'
import csv, sys
path = sys.argv[1]
tmp  = path + ".tmp"
with open(path, newline="", encoding="utf-8") as f:
    reader = csv.reader(f)
    header = next(reader)
    rows   = sorted(reader, key=lambda r: r[0] if r else "")
with open(tmp, "w", newline="", encoding="utf-8") as f:
    writer = csv.writer(f)
    writer.writerow(header)
    writer.writerows(rows)
import os; os.replace(tmp, path)
print(f"Sorted. Total rows: {len(rows)}")
PYEOF

echo ""
echo "=== Splitting by province ==="
python3 - "$MERGED" "$DATA" <<'PYEOF'
import csv, os, sys, re

PROVINCE_NAMES = {
    "01":"ha-noi","04":"cao-bang","08":"tuyen-quang","11":"dien-bien",
    "12":"lai-chau","14":"son-la","15":"lao-cai","19":"thai-nguyen",
    "20":"lang-son","22":"quang-ninh","24":"bac-ninh","25":"phu-tho",
    "31":"hai-phong","33":"hung-yen","37":"ninh-binh","38":"thanh-hoa",
    "40":"nghe-an","42":"ha-tinh","44":"quang-tri","46":"hue",
    "48":"da-nang","51":"quang-ngai","52":"gia-lai","56":"khanh-hoa",
    "66":"dak-lak","68":"lam-dong","75":"dong-nai","79":"ho-chi-minh",
    "80":"tay-ninh","82":"dong-thap","86":"vinh-long","91":"an-giang",
    "92":"can-tho","96":"ca-mau",
}

src, data_dir = sys.argv[1], sys.argv[2]
writers = {}
files   = {}

with open(src, newline="", encoding="utf-8") as f:
    reader = csv.reader(f)
    header = next(reader)
    for row in reader:
        code = row[0][:2] if row else ""
        if code not in writers:
            name    = PROVINCE_NAMES.get(code, f"tinh-{code}")
            fname   = os.path.join(data_dir, f"{code}-{name}.csv")
            fh      = open(fname, "w", newline="", encoding="utf-8")
            files[code]   = fh
            writers[code] = csv.writer(fh)
            writers[code].writerow(header)
        writers[code].writerow(row)

for fh in files.values():
    fh.close()

print("Province files written:")
for code in sorted(writers):
    name = PROVINCE_NAMES.get(code, f"tinh-{code}")
    print(f"  {code}-{name}.csv")
PYEOF

echo ""
echo "=== Stats per province ==="
python3 - "$DATA" <<'PYEOF'
import csv, os, glob
rows = []
for f in sorted(glob.glob(os.path.join(sys.argv[1], "??.*.csv"))):
    with open(f, newline="", encoding="utf-8") as fh:
        n = sum(1 for _ in fh) - 1
    rows.append((os.path.basename(f), n))
import sys
for name, n in rows:
    print(f"  {name}: {n:,}")
total = sum(n for _, n in rows)
print(f"\nTotal unique students: {total:,}")
PYEOF

echo ""
echo "Done! Dataset in $DATA/"
