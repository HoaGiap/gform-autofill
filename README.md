# ⚡ GForm AutoFill Tool

Công cụ tự động điền và gửi Google Forms sử dụng Python + Playwright.

---

## 📦 Cài đặt

### Yêu cầu
- Python 3.10+
- pip

### Các bước

```bash
# 1. Clone/tải project
cd gform-autofill

# 2. Cài dependencies
pip install -r requirements.txt

# 3. Cài Chromium (chỉ cần làm 1 lần)
playwright install chromium

# 4. Khởi động web app
python app.py
# Mở trình duyệt: http://localhost:5000
```

---

## 🖥️ Giao diện Web

Mở `http://localhost:5000` để dùng giao diện web với đầy đủ tính năng:

- Nhập URL form
- Upload file JSON/CSV/XLSX hoặc nhập JSON trực tiếp
- Cấu hình số lần gửi, proxy, headless mode
- Xem log real-time và kết quả

---

## 💻 Dùng CLI

```bash
# Điền ngẫu nhiên, 1 lần
python form_filler.py --url "https://docs.google.com/forms/d/..." --random

# Dùng file JSON, 3 lần gửi
python form_filler.py --url "https://..." --data examples/answers.json --repeat 3

# Dùng file CSV, hiển thị trình duyệt
python form_filler.py --url "https://..." --data examples/answers.csv --headful

# Dùng proxy
python form_filler.py --url "https://..." --random --proxy "http://user:pass@host:3128"
```

### Tham số CLI

| Tham số | Mô tả | Mặc định |
|---------|-------|---------|
| `--url` | URL Google Form (bắt buộc) | — |
| `--data` | File JSON/CSV/XLSX câu trả lời | — |
| `--random` | Điền ngẫu nhiên | False |
| `--repeat` | Số lần gửi | 1 |
| `--headful` | Hiển thị trình duyệt | False (headless) |
| `--proxy` | Proxy URL | — |

---

## 📋 Format file dữ liệu

### JSON (`answers.json`)
```json
{
  "Tiêu đề câu hỏi": "Câu trả lời",
  "Câu hỏi radio": "Một đáp án",
  "Câu hỏi checkbox": ["Đáp án 1", "Đáp án 2"],
  "Câu hỏi text": "Nội dung tự do",
  "Câu hỏi dropdown": "Chọn mục này",
  "Thang điểm": "5"
}
```

### CSV (`answers.csv`)
```csv
question,answer
Họ và tên,Nguyễn Văn A
Email,test@example.com
Đánh giá,Rất tốt
```

> **Lưu ý:** Key trong JSON/CSV phải **khớp chính xác** với tiêu đề câu hỏi trong form (không cần dấu `*`).

---

## 🎯 Các loại câu hỏi được hỗ trợ

| Loại | Hỗ trợ | Ghi chú |
|------|--------|---------|
| Radio (trắc nghiệm 1 đáp án) | ✅ | Tìm khớp theo text |
| Checkbox (nhiều đáp án) | ✅ | Truyền array hoặc string |
| Text ngắn | ✅ | — |
| Đoạn văn (paragraph) | ✅ | — |
| Dropdown | ✅ | — |
| Linear Scale (thang điểm) | ✅ | Truyền số "1"-"5" |
| Multiple Choice Grid | ✅ | Truyền dict {row: answer} |
| Date / Time | ⚠️ | Hỗ trợ cơ bản |

---

## ⚙️ Cấu hình nâng cao

### Dùng Proxy
```bash
python form_filler.py --url "..." --proxy "http://user:pass@host:port"
```

### Form yêu cầu đăng nhập Google
1. Đăng nhập Chrome bình thường
2. Export cookies (dùng extension EditThisCookie)
3. Đặt file cookies vào `cookies.json`
4. Tool sẽ tự load cookies

### Điều chỉnh tốc độ
Trong `form_filler.py`, chỉnh `human_delay()`:
```python
await human_delay(min_ms=500, max_ms=2000)  # Chậm hơn
await human_delay(min_ms=100, max_ms=300)   # Nhanh hơn
```

---

## 📁 Cấu trúc Project

```
gform-autofill/
├── form_filler.py     # Engine tự động hóa chính
├── app.py             # Flask web server
├── requirements.txt   # Dependencies
├── templates/
│   └── index.html     # Giao diện web
├── examples/
│   ├── answers.json   # File JSON mẫu
│   └── answers.csv    # File CSV mẫu
└── logs/
    ├── filler.log     # Log tổng hợp
    └── result_*.json  # Log từng lần gửi
```

---

## ⚠️ Lưu ý

- Tool này chỉ nên dùng cho **form của bạn** hoặc khi **có sự đồng ý** của chủ form.
- Google có thể phát hiện automation — dùng `human_delay` và proxy để giảm thiểu.
- Không gửi quá nhiều lần từ cùng một IP trong thời gian ngắn.

---

## 🐛 Xử lý lỗi thường gặp

| Lỗi | Giải pháp |
|-----|-----------|
| `Playwright chưa cài` | Chạy `pip install playwright && playwright install chromium` |
| `Form yêu cầu đăng nhập` | Đăng nhập thủ công, export cookies |
| `Không tìm thấy nút Gửi` | Form có thể dùng selector khác, kiểm tra `--headful` |
| `Timeout` | Tăng timeout trong `page.goto(..., timeout=60000)` |
