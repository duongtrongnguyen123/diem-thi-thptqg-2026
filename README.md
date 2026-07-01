# Điểm thi THPT Quốc gia 2026

Bộ dữ liệu điểm thi tốt nghiệp THPT năm 2026 của **1.200.202 thí sinh** toàn quốc (34 tỉnh/thành phố sau khi sắp xếp lại đơn vị hành chính).

Dữ liệu thu thập từ trang tra cứu công khai của VietnamNet ngày 01/07/2026.

---

## Cấu trúc dữ liệu

### Thư mục `data/`

| File | Mô tả |
|------|-------|
| `diem_thi_thptqg_2026_all.csv` | Toàn quốc, đã loại trùng, sắp xếp theo SBD |
| `01-ha-noi.csv` | Hà Nội |
| `04-cao-bang.csv` | Cao Bằng |
| `08-tuyen-quang.csv` | Tuyên Quang |
| `11-dien-bien.csv` | Điện Biên |
| `12-lai-chau.csv` | Lai Châu |
| `14-son-la.csv` | Sơn La |
| `15-lao-cai.csv` | Lào Cai |
| `19-thai-nguyen.csv` | Thái Nguyên |
| `20-lang-son.csv` | Lạng Sơn |
| `22-quang-ninh.csv` | Quảng Ninh |
| `24-bac-ninh.csv` | Bắc Ninh |
| `25-phu-tho.csv` | Phú Thọ |
| `31-hai-phong.csv` | Hải Phòng |
| `33-hung-yen.csv` | Hưng Yên |
| `37-ninh-binh.csv` | Ninh Bình |
| `38-thanh-hoa.csv` | Thanh Hóa |
| `40-nghe-an.csv` | Nghệ An |
| `42-ha-tinh.csv` | Hà Tĩnh |
| `44-quang-tri.csv` | Quảng Trị |
| `46-hue.csv` | Huế |
| `48-da-nang.csv` | Đà Nẵng |
| `51-quang-ngai.csv` | Quảng Ngãi |
| `52-gia-lai.csv` | Gia Lai |
| `56-khanh-hoa.csv` | Khánh Hòa |
| `66-dak-lak.csv` | Đắk Lắk |
| `68-lam-dong.csv` | Lâm Đồng |
| `75-dong-nai.csv` | Đồng Nai |
| `79-ho-chi-minh.csv` | Hồ Chí Minh |
| `80-tay-ninh.csv` | Tây Ninh |
| `82-dong-thap.csv` | Đồng Tháp |
| `86-vinh-long.csv` | Vĩnh Long |
| `91-an-giang.csv` | An Giang |
| `92-can-tho.csv` | Cần Thơ |
| `96-ca-mau.csv` | Cà Mau |

### Cột CSV

| Cột | Ý nghĩa |
|-----|---------|
| `sbd` | Số báo danh (8 chữ số: 2 mã tỉnh + 6 số thứ tự) |
| `province_code` | Mã tỉnh (2 chữ số đầu của SBD) |
| `province_name` | Tên tỉnh/thành phố |
| `toan` | Toán |
| `ngu_van` | Ngữ văn |
| `ngoai_ngu` | Ngoại ngữ |
| `vat_li` | Vật lý |
| `hoa_hoc` | Hóa học |
| `sinh_hoc` | Sinh học |
| `lich_su` | Lịch sử |
| `dia_li` | Địa lý |
| `gdcd` | Giáo dục công dân |
| `tin_hoc` | Tin học |
| `cong_nghe` | Công nghệ |
| `extra` | Môn khác (nếu có) |

Điểm còn trống (`""`) = thí sinh không thi môn đó.

---

## Ví dụ sử dụng

### Python / pandas
```python
import pandas as pd

# Toàn quốc
df = pd.read_csv("data/diem_thi_thptqg_2026_all.csv", dtype={"sbd": str, "province_code": str})

# Một tỉnh
hn = pd.read_csv("data/01-ha-noi.csv", dtype={"sbd": str})

# Điểm trung bình Toán theo tỉnh
print(df.groupby("province_name")["toan"].mean().sort_values(ascending=False))
```

### Tra cứu theo SBD
```python
row = df[df["sbd"] == "22010737"].iloc[0]
print(row.to_dict())
```

---

## Lưu ý

- Dữ liệu thu thập từ trang tra cứu **công khai** của VietnamNet (01/07/2026).
- Đây là dữ liệu **cá nhân** — chỉ dùng cho mục đích nghiên cứu, phân tích cá nhân. Không tái xuất bản hoặc thương mại hóa.
- Một số thí sinh có thể bị thiếu nếu SBD không liên tục hoặc đã được chỉnh sửa sau khi thu thập.

---

## Thu thập dữ liệu

Sử dụng scraper bất đồng bộ (async) viết bằng Python + aiohttp:

```bash
# Cài đặt
python3 -m venv .venv && .venv/bin/pip install aiohttp

# Thu thập một tỉnh (ví dụ: Quảng Ninh - mã 22)
.venv/bin/python scripts/scraper_async.py --prefixes 22 --out data/22-quang-ninh.csv
```

Xem `scripts/scraper_async.py` để biết thêm tùy chọn (`--workers`, `--max-miss`, v.v.).
