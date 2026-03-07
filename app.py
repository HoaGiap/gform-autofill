"""
Flask Web Server cho Google Form Auto-Fill Tool
Cung cấp giao diện web để người dùng tương tác với tool.
"""

import asyncio
import json
import os
import threading
import uuid
from datetime import datetime
from pathlib import Path

from flask import Flask, jsonify, render_template, request, send_file

app = Flask(__name__)
app.config["MAX_CONTENT_LENGTH"] = 5 * 1024 * 1024  # 5 MB

LOG_DIR = Path("logs")
LOG_DIR.mkdir(exist_ok=True)

# Lưu trạng thái các job đang chạy
jobs: dict[str, dict] = {}


# ─── Helpers ──────────────────────────────────────────────────────────────────

def parse_answers_from_text(raw: str) -> dict:
    """Parse chuỗi text dạng 'Câu hỏi: Câu trả lời' hoặc JSON."""
    raw = raw.strip()
    if not raw:
        return {}
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        pass
    # Thử parse dạng "key: value" (mỗi dòng)
    answers = {}
    for line in raw.splitlines():
        if ":" in line:
            k, _, v = line.partition(":")
            answers[k.strip()] = v.strip()
    return answers


def run_fill_job(job_id: str, url: str, answers: dict, fill_random: bool, repeat: int, headless: bool, proxy: str):
    """Chạy fill job trong thread riêng."""
    from form_filler import GoogleFormFiller

    jobs[job_id]["status"] = "running"
    jobs[job_id]["logs"] = []
    jobs[job_id]["start_time"] = datetime.now().isoformat()

    # Ghi log vào job
    import logging

    class JobLogHandler(logging.Handler):
        def emit(self, record):
            jobs[job_id]["logs"].append({
                "time": datetime.now().strftime("%H:%M:%S"),
                "level": record.levelname,
                "msg": self.format(record),
            })

    handler = JobLogHandler()
    handler.setFormatter(logging.Formatter("%(message)s"))
    filler_logger = logging.getLogger("gform_filler")
    filler_logger.addHandler(handler)

    try:
        proxy_cfg = {"server": proxy} if proxy else None
        filler = GoogleFormFiller(headless=headless, proxy=proxy_cfg)

        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        results = loop.run_until_complete(
            filler.fill_and_submit(
                url=url,
                answers=answers,
                fill_random=fill_random,
                repeat=repeat,
            )
        )
        loop.close()

        jobs[job_id]["results"] = results
        jobs[job_id]["status"] = "done"
        success = sum(1 for r in results if r["success"])
        jobs[job_id]["summary"] = {
            "total": len(results),
            "success": success,
            "failed": len(results) - success,
        }
    except Exception as e:
        jobs[job_id]["status"] = "error"
        jobs[job_id]["error"] = str(e)
        jobs[job_id]["logs"].append({
            "time": datetime.now().strftime("%H:%M:%S"),
            "level": "ERROR",
            "msg": f"Job lỗi: {e}",
        })
    finally:
        filler_logger.removeHandler(handler)
        jobs[job_id]["end_time"] = datetime.now().isoformat()


# ─── Routes ───────────────────────────────────────────────────────────────────

@app.route("/")
def index():
    return render_template("index.html")


@app.route("/api/run", methods=["POST"])
def api_run():
    """Khởi chạy một fill job mới."""
    data = request.get_json(force=True)

    url = data.get("url", "").strip()
    if not url:
        return jsonify({"error": "URL không được để trống"}), 400
    if "docs.google.com/forms" not in url and "forms.gle" not in url:
        return jsonify({"error": "URL không hợp lệ. Phải là Google Form."}), 400

    # Parse answers
    answers_raw = data.get("answers", "")
    if isinstance(answers_raw, dict):
        answers = answers_raw
    else:
        answers = parse_answers_from_text(answers_raw)

    fill_random = data.get("fill_random", True)
    repeat = max(1, min(int(data.get("repeat", 1)), 100))  # Giới hạn 100 lần
    headless = data.get("headless", True)
    proxy = data.get("proxy", "").strip()

    job_id = str(uuid.uuid4())[:8]
    jobs[job_id] = {
        "id": job_id,
        "url": url,
        "status": "queued",
        "answers": answers,
        "repeat": repeat,
        "logs": [],
        "results": [],
        "created": datetime.now().isoformat(),
    }

    t = threading.Thread(
        target=run_fill_job,
        args=(job_id, url, answers, fill_random, repeat, headless, proxy),
        daemon=True,
    )
    t.start()

    return jsonify({"job_id": job_id, "message": "Job đã được tạo"})


@app.route("/api/job/<job_id>")
def api_job_status(job_id):
    """Lấy trạng thái và log của một job."""
    job = jobs.get(job_id)
    if not job:
        return jsonify({"error": "Không tìm thấy job"}), 404
    return jsonify(job)


@app.route("/api/jobs")
def api_jobs():
    """Danh sách tất cả jobs."""
    return jsonify(list(jobs.values()))


@app.route("/api/logs")
def api_logs():
    """Đọc file log chung."""
    log_file = LOG_DIR / "filler.log"
    if not log_file.exists():
        return jsonify({"lines": []})
    with open(log_file, encoding="utf-8") as f:
        lines = f.readlines()[-100:]  # 100 dòng cuối
    return jsonify({"lines": [l.rstrip() for l in lines]})


@app.route("/api/example-json")
def api_example_json():
    """Trả về file JSON mẫu."""
    example = {
        "Họ và tên": "Nguyễn Văn A",
        "Email": "nguyenvana@example.com",
        "Bạn đánh giá dịch vụ như thế nào?": "Rất tốt",
        "Bạn có muốn nhận thông báo không?": ["Có", "Email"],
        "Nhận xét của bạn": "Dịch vụ rất tốt, tôi rất hài lòng!",
        "Điểm đánh giá": "5",
    }
    tmp = Path("/tmp/example_answers.json")
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(example, f, ensure_ascii=False, indent=2)
    return send_file(tmp, as_attachment=True, download_name="example_answers.json")


@app.route("/api/example-csv")
def api_example_csv():
    """Trả về file CSV mẫu."""
    content = "question,answer\nHọ và tên,Nguyễn Văn A\nEmail,test@example.com\nĐánh giá,Tốt\nNhận xét,Hài lòng với dịch vụ\n"
    tmp = Path("/tmp/example_answers.csv")
    tmp.write_text(content, encoding="utf-8")
    return send_file(tmp, as_attachment=True, download_name="example_answers.csv")


@app.route("/api/upload", methods=["POST"])
def api_upload():
    """Upload file JSON/CSV và parse answers."""
    if "file" not in request.files:
        return jsonify({"error": "Không có file"}), 400

    file = request.files["file"]
    filename = file.filename.lower()

    try:
        if filename.endswith(".json"):
            content = file.read().decode("utf-8")
            answers = json.loads(content)
        elif filename.endswith(".csv"):
            import csv
            import io
            content = file.read().decode("utf-8")
            reader = csv.DictReader(io.StringIO(content))
            rows = list(reader)
            # Hỗ trợ 2 format: {question, answer} hoặc {key: value}
            if rows and "question" in rows[0] and "answer" in rows[0]:
                answers = {r["question"]: r["answer"] for r in rows}
            else:
                # Mỗi row là một câu hỏi, cột đầu = tên, cột 2 = trả lời
                answers = {}
                for row in rows:
                    vals = list(row.values())
                    if len(vals) >= 2:
                        answers[vals[0]] = vals[1]
        elif filename.endswith((".xlsx", ".xls")):
            import pandas as pd
            import io
            df = pd.read_excel(io.BytesIO(file.read()))
            answers = dict(zip(df.iloc[:, 0].astype(str), df.iloc[:, 1].astype(str)))
        else:
            return jsonify({"error": "Chỉ hỗ trợ JSON, CSV, XLSX"}), 400

        return jsonify({"answers": answers, "count": len(answers)})
    except Exception as e:
        return jsonify({"error": f"Lỗi đọc file: {e}"}), 400


if __name__ == "__main__":
    print("=" * 50)
    print("🚀 Google Form Auto-Fill Tool")
    print("=" * 50)
    print("Mở trình duyệt: http://localhost:5000")
    print("=" * 50)
    app.run(debug=False, host="0.0.0.0", port=5000)
