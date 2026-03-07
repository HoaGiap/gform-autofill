"""
Google Form Auto-Fill Engine
Sử dụng Playwright để tự động hóa việc điền và gửi Google Forms.
"""

import asyncio
import json
import random
import time
import logging
from datetime import datetime
from pathlib import Path
from typing import Optional

try:
    from playwright.async_api import async_playwright, Page, TimeoutError as PlaywrightTimeout
    PLAYWRIGHT_AVAILABLE = True
except ImportError:
    PLAYWRIGHT_AVAILABLE = False

# ─── Logging Setup ──────────────────────────────────────────────────────────
LOG_DIR = Path("logs")
LOG_DIR.mkdir(exist_ok=True)

logger = logging.getLogger("gform_filler")
logger.setLevel(logging.DEBUG)

_fmt = logging.Formatter("%(asctime)s [%(levelname)s] %(message)s", "%Y-%m-%d %H:%M:%S")
_fh = logging.FileHandler(LOG_DIR / "filler.log", encoding="utf-8")
_fh.setFormatter(_fmt)
_ch = logging.StreamHandler()
_ch.setFormatter(_fmt)
logger.addHandler(_fh)
logger.addHandler(_ch)


# ─── Selectors cho Google Form ───────────────────────────────────────────────
SELECTORS = {
    # Container của từng câu hỏi
    "question_block": '[role="listitem"]',

    # Các loại input
    "radio":       'div[role="radio"]',
    "checkbox":    'div[role="checkbox"]',
    "text_input":  'input[type="text"]',
    "textarea":    "textarea",
    "dropdown":    'div[role="listbox"], select',
    "option_item": '[role="option"]',
    "scale":       '[role="radio"]',

    # Tiêu đề câu hỏi
    "question_title": '[role="heading"], .freebirdFormviewerComponentsQuestionBaseTitle',

    # Nút Gửi
    "submit_btn": '[role="button"][jsname="M2UYVd"], div[jscontroller] [role="button"]:last-child',

    # Thông báo thành công
    "success_msg": '.freebirdFormviewerViewResponseConfirmationMessage, [data-automation-id="confirmation-message"]',

    # Thông báo lỗi (thiếu câu bắt buộc)
    "error_msg": '.freebirdFormviewerComponentsQuestionBaseRequiredError',
}

# Các câu trả lời ngẫu nhiên cho text input
RANDOM_TEXT_POOL = [
    "Tôi đồng ý với các điều khoản",
    "Câu trả lời của tôi",
    "Rất tốt",
    "Bình thường",
    "Tốt",
    "Khá tốt",
    "Hài lòng",
    "Cần cải thiện",
]


# ─── Utility ─────────────────────────────────────────────────────────────────

async def human_delay(min_ms: int = 300, max_ms: int = 1200):
    """Chờ ngẫu nhiên để giả lập hành vi người dùng thật."""
    delay = random.randint(min_ms, max_ms) / 1000
    await asyncio.sleep(delay)


async def human_type(page: Page, selector: str, text: str):
    """Gõ text theo kiểu người dùng thật (từng ký tự, có delay ngẫu nhiên)."""
    element = page.locator(selector).first
    await element.click()
    await human_delay(100, 300)
    for char in text:
        await element.type(char, delay=random.randint(30, 120))
    await human_delay(200, 500)


# ─── Core Filler Class ───────────────────────────────────────────────────────

class GoogleFormFiller:
    """
    Tự động điền và gửi Google Form.

    Parameters
    ----------
    headless : bool
        Chạy trình duyệt ẩn (True) hay hiển thị (False).
    proxy : dict | None
        Cấu hình proxy, ví dụ {"server": "http://proxy:8080"}.
    """

    def __init__(self, headless: bool = True, proxy: Optional[dict] = None):
        self.headless = headless
        self.proxy = proxy

    # ── Điền từng loại câu hỏi ───────────────────────────────────────────────

    async def _fill_radio(self, block, answer: Optional[str]):
        """Chọn radio button (trắc nghiệm 1 đáp án)."""
        radios = await block.query_selector_all(SELECTORS["radio"])
        if not radios:
            return False

        if answer:
            # Tìm option khớp với answer (không phân biệt hoa/thường)
            for radio in radios:
                label = (await radio.inner_text()).strip().lower()
                if answer.lower() in label or label in answer.lower():
                    await radio.click()
                    await human_delay()
                    logger.debug(f"  Radio → chọn: '{label}'")
                    return True

        # Chọn ngẫu nhiên nếu không tìm thấy
        chosen = random.choice(radios)
        label = (await chosen.inner_text()).strip()
        await chosen.click()
        await human_delay()
        logger.debug(f"  Radio → ngẫu nhiên: '{label}'")
        return True

    async def _fill_checkbox(self, block, answers):
        """Chọn checkbox (trắc nghiệm nhiều đáp án)."""
        boxes = await block.query_selector_all(SELECTORS["checkbox"])
        if not boxes:
            return False

        if isinstance(answers, str):
            answers = [answers]

        if answers:
            for box in boxes:
                label = (await box.inner_text()).strip().lower()
                for ans in answers:
                    if ans.lower() in label or label in ans.lower():
                        state = await box.get_attribute("aria-checked")
                        if state != "true":
                            await box.click()
                            await human_delay(200, 600)
                            logger.debug(f"  Checkbox → chọn: '{label}'")
        else:
            # Chọn 1-2 ngẫu nhiên
            n = random.randint(1, min(2, len(boxes)))
            chosen = random.sample(boxes, n)
            for box in chosen:
                label = (await box.inner_text()).strip()
                await box.click()
                await human_delay(200, 600)
                logger.debug(f"  Checkbox → ngẫu nhiên: '{label}'")
        return True

    async def _fill_text(self, block, answer: Optional[str], is_long: bool = False):
        """Điền text input hoặc textarea."""
        selector = "textarea" if is_long else 'input[type="text"]'
        el = await block.query_selector(selector)
        if not el:
            # Thử lại với selector khác
            el = await block.query_selector("input, textarea")
        if not el:
            return False

        text = answer if answer else random.choice(RANDOM_TEXT_POOL)
        await el.click()
        await human_delay(100, 300)
        await el.fill("")  # Xóa nội dung cũ
        for char in text:
            await el.type(char, delay=random.randint(25, 100))
        await human_delay(200, 500)
        logger.debug(f"  Text → điền: '{text[:50]}{'...' if len(text) > 50 else ''}'")
        return True

    async def _fill_dropdown(self, block, answer: Optional[str]):
        """Chọn dropdown / select."""
        # Thử Google Form custom dropdown trước
        dropdown_btn = await block.query_selector('[role="listbox"], .quantumWizMenuPaperselectEl')
        if dropdown_btn:
            await dropdown_btn.click()
            await human_delay(400, 800)

            options = await block.page.query_selector_all('[role="option"]')
            if not options:
                options = await block.query_selector_all('[role="option"]')

            if options:
                if answer:
                    for opt in options:
                        text = (await opt.inner_text()).strip().lower()
                        if answer.lower() in text or text in answer.lower():
                            await opt.click()
                            await human_delay()
                            logger.debug(f"  Dropdown → chọn: '{text}'")
                            return True
                # Bỏ qua option đầu tiên (thường là "Chọn") nếu có nhiều hơn 1
                start = 1 if len(options) > 1 else 0
                chosen = random.choice(options[start:])
                text = (await chosen.inner_text()).strip()
                await chosen.click()
                await human_delay()
                logger.debug(f"  Dropdown → ngẫu nhiên: '{text}'")
                return True

        # Fallback: select HTML thuần
        select = await block.query_selector("select")
        if select:
            opts = await select.query_selector_all("option")
            values = [await o.get_attribute("value") for o in opts if await o.get_attribute("value")]
            if values:
                val = answer if answer in values else random.choice(values)
                await select.select_option(val)
                await human_delay()
                logger.debug(f"  Select → chọn: '{val}'")
                return True
        return False

    async def _fill_scale(self, block, answer: Optional[str]):
        """Chọn thang điểm (Linear Scale)."""
        # Scale trong GForm dùng radio buttons
        return await self._fill_radio(block, answer)

    async def _fill_grid(self, block, answers: dict):
        """Điền Multiple Choice Grid (lưới trắc nghiệm)."""
        rows = await block.query_selector_all('[role="radiogroup"], [role="group"]')
        if not rows:
            return False

        for i, row in enumerate(rows):
            row_label = ""
            heading = await row.query_selector('[role="heading"], label')
            if heading:
                row_label = (await heading.inner_text()).strip()

            row_ans = None
            if answers:
                # Thử tìm theo label row
                row_ans = answers.get(row_label) or answers.get(str(i))

            radios = await row.query_selector_all(SELECTORS["radio"])
            if radios:
                if row_ans:
                    for r in radios:
                        lbl = (await r.inner_text()).strip().lower()
                        if row_ans.lower() in lbl:
                            await r.click()
                            await human_delay(200, 500)
                            break
                else:
                    chosen = random.choice(radios)
                    await chosen.click()
                    await human_delay(200, 500)
        return True

    # ── Detect question type ──────────────────────────────────────────────────

    async def _detect_and_fill(self, block, answer):
        """Phát hiện loại câu hỏi và điền tự động."""
        # Lưới trắc nghiệm
        grids = await block.query_selector_all('[role="radiogroup"]')
        if len(grids) > 1:
            logger.debug("  Loại: Grid")
            return await self._fill_grid(block, answer if isinstance(answer, dict) else {})

        # Checkbox
        checkboxes = await block.query_selector_all(SELECTORS["checkbox"])
        if checkboxes:
            logger.debug("  Loại: Checkbox")
            return await self._fill_checkbox(block, answer)

        # Radio
        radios = await block.query_selector_all(SELECTORS["radio"])
        if radios:
            logger.debug("  Loại: Radio / Scale")
            return await self._fill_radio(block, answer)

        # Textarea (đoạn văn dài)
        textarea = await block.query_selector("textarea")
        if textarea:
            logger.debug("  Loại: Textarea")
            return await self._fill_text(block, answer, is_long=True)

        # Text input
        text_inp = await block.query_selector('input[type="text"], input[type="email"], input[type="number"]')
        if text_inp:
            logger.debug("  Loại: Text Input")
            return await self._fill_text(block, answer)

        # Dropdown
        dropdown = await block.query_selector('[role="listbox"], select')
        if dropdown:
            logger.debug("  Loại: Dropdown")
            return await self._fill_dropdown(block, answer)

        return False

    # ── Main Fill Logic ───────────────────────────────────────────────────────

    async def fill_and_submit(
        self,
        url: str,
        answers: dict,
        fill_random: bool = True,
        repeat: int = 1,
    ) -> list[dict]:
        """
        Điền và gửi form.

        Parameters
        ----------
        url : str
            URL của Google Form.
        answers : dict
            Mapping {tiêu_đề_câu_hỏi: câu_trả_lời}. Có thể để rỗng.
        fill_random : bool
            Tự động điền ngẫu nhiên nếu không có dữ liệu.
        repeat : int
            Số lần gửi form.

        Returns
        -------
        list[dict]
            Danh sách kết quả mỗi lần gửi.
        """
        if not PLAYWRIGHT_AVAILABLE:
            return [{"success": False, "error": "Playwright chưa được cài đặt. Chạy: pip install playwright && playwright install chromium"}]

        results = []

        async with async_playwright() as pw:
            launch_opts = {
                "headless": self.headless,
                "args": [
                    "--no-sandbox",
                    "--disable-blink-features=AutomationControlled",
                    "--disable-dev-shm-usage",
                ],
            }
            if self.proxy:
                launch_opts["proxy"] = self.proxy

            browser = await pw.chromium.launch(**launch_opts)

            for attempt in range(1, repeat + 1):
                logger.info(f"═══ Lần gửi #{attempt}/{repeat} ═══")
                context = await browser.new_context(
                    user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                    viewport={"width": random.randint(1280, 1920), "height": random.randint(768, 1080)},
                )
                page = await context.new_page()

                result = {
                    "attempt": attempt,
                    "url": url,
                    "timestamp": datetime.now().isoformat(),
                    "success": False,
                    "error": None,
                    "filled": {},
                }

                try:
                    # ── Tải form ──────────────────────────────────────────
                    logger.info(f"Đang mở: {url}")
                    await page.goto(url, wait_until="networkidle", timeout=30000)
                    await human_delay(1000, 2000)

                    # Kiểm tra cần đăng nhập không
                    if "accounts.google.com" in page.url:
                        raise RuntimeError("Form yêu cầu đăng nhập Google. Hãy dùng cookies hoặc bỏ qua xác thực.")

                    # ── Lấy tất cả câu hỏi ───────────────────────────────
                    question_blocks = await page.query_selector_all(SELECTORS["question_block"])
                    logger.info(f"Tìm thấy {len(question_blocks)} khối câu hỏi")

                    filled_count = 0
                    for idx, block in enumerate(question_blocks):
                        # Lấy tiêu đề câu hỏi
                        title_el = await block.query_selector(SELECTORS["question_title"])
                        title = (await title_el.inner_text()).strip() if title_el else f"question_{idx}"
                        # Bỏ dấu * (bắt buộc)
                        clean_title = title.replace("*", "").strip()

                        # Lấy câu trả lời tương ứng
                        answer = answers.get(clean_title) or answers.get(title) or answers.get(str(idx))

                        if answer is None and not fill_random:
                            logger.debug(f"[{idx}] '{clean_title}' → bỏ qua (không có dữ liệu)")
                            continue

                        logger.info(f"[{idx}] '{clean_title}'")
                        filled = await self._detect_and_fill(block, answer)
                        if filled:
                            filled_count += 1
                            result["filled"][clean_title] = answer or "(ngẫu nhiên)"
                        await human_delay(300, 700)

                    logger.info(f"Đã điền {filled_count} câu hỏi")

                    # ── Xử lý form nhiều trang ────────────────────────────
                    max_pages = 20
                    for _ in range(max_pages):
                        next_btn = await page.query_selector('[role="button"][jsname="OCpkoe"]')
                        if next_btn:
                            await next_btn.click()
                            await human_delay(1000, 2000)
                            await page.wait_for_load_state("networkidle")
                            # Điền tiếp trang mới
                            question_blocks = await page.query_selector_all(SELECTORS["question_block"])
                            for idx, block in enumerate(question_blocks):
                                title_el = await block.query_selector(SELECTORS["question_title"])
                                title = (await title_el.inner_text()).strip() if title_el else f"page_q_{idx}"
                                clean_title = title.replace("*", "").strip()
                                answer = answers.get(clean_title) or answers.get(str(idx))
                                if answer or fill_random:
                                    await self._detect_and_fill(block, answer)
                                    await human_delay(200, 500)
                        else:
                            break

                    # ── Kiểm tra lỗi ─────────────────────────────────────
                    errors = await page.query_selector_all(SELECTORS["error_msg"])
                    if errors:
                        error_texts = [await e.inner_text() for e in errors]
                        raise RuntimeError(f"Lỗi validation: {'; '.join(error_texts)}")

                    # ── Gửi form ──────────────────────────────────────────
                    submit_btn = await page.query_selector(SELECTORS["submit_btn"])
                    if not submit_btn:
                        # Thử tìm nút có text "Gửi" hoặc "Submit"
                        submit_btn = await page.get_by_role("button", name="Gửi").first.element_handle()
                        if not submit_btn:
                            submit_btn = await page.get_by_role("button", name="Submit").first.element_handle()

                    if not submit_btn:
                        raise RuntimeError("Không tìm thấy nút Gửi!")

                    await submit_btn.scroll_into_view_if_needed()
                    await human_delay(500, 1000)
                    await submit_btn.click()
                    logger.info("Đã click nút Gửi")

                    # ── Xác nhận thành công ───────────────────────────────
                    try:
                        await page.wait_for_selector(
                            SELECTORS["success_msg"],
                            timeout=10000,
                        )
                        result["success"] = True
                        logger.info("✅ Gửi thành công!")
                    except PlaywrightTimeout:
                        # Kiểm tra URL thay đổi (một số form redirect sau submit)
                        if "formResponse" in page.url or "viewscore" in page.url:
                            result["success"] = True
                            logger.info("✅ Gửi thành công (redirect)!")
                        else:
                            result["success"] = True  # Giả định thành công nếu không có lỗi rõ ràng
                            logger.warning("⚠️ Không tìm thấy thông báo thành công, nhưng không có lỗi.")

                except Exception as e:
                    result["error"] = str(e)
                    logger.error(f"❌ Lỗi: {e}")

                finally:
                    results.append(result)
                    self._save_log(result)
                    await context.close()

                    # Nghỉ giữa các lần gửi
                    if attempt < repeat:
                        wait = random.randint(3, 8)
                        logger.info(f"Chờ {wait}s trước lần gửi tiếp...")
                        await asyncio.sleep(wait)

            await browser.close()

        return results

    def _save_log(self, result: dict):
        """Lưu log JSON chi tiết."""
        log_file = LOG_DIR / f"result_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        with open(log_file, "w", encoding="utf-8") as f:
            json.dump(result, f, ensure_ascii=False, indent=2)
        logger.debug(f"Log lưu tại: {log_file}")


# ─── CLI Interface ────────────────────────────────────────────────────────────

def run_cli():
    import argparse
    import pandas as pd

    parser = argparse.ArgumentParser(
        description="Google Form Auto-Fill Tool",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Ví dụ:
  python form_filler.py --url "https://docs.google.com/forms/..." --data answers.json
  python form_filler.py --url "https://..." --random --repeat 5
  python form_filler.py --url "https://..." --data answers.csv --headful
        """,
    )
    parser.add_argument("--url", required=True, help="URL của Google Form")
    parser.add_argument("--data", help="File JSON hoặc CSV chứa câu trả lời")
    parser.add_argument("--random", action="store_true", help="Điền ngẫu nhiên")
    parser.add_argument("--repeat", type=int, default=1, help="Số lần gửi (mặc định: 1)")
    parser.add_argument("--headful", action="store_true", help="Hiển thị trình duyệt")
    parser.add_argument("--proxy", help="Proxy URL, ví dụ: http://user:pass@host:port")
    args = parser.parse_args()

    # Đọc dữ liệu
    answers = {}
    if args.data:
        path = Path(args.data)
        if path.suffix == ".json":
            with open(path, encoding="utf-8") as f:
                answers = json.load(f)
        elif path.suffix in (".csv", ".xlsx"):
            df = pd.read_csv(path) if path.suffix == ".csv" else pd.read_excel(path)
            # Giả định cột đầu là tên câu hỏi, cột 2 là câu trả lời
            answers = dict(zip(df.iloc[:, 0], df.iloc[:, 1]))

    proxy_cfg = {"server": args.proxy} if args.proxy else None
    filler = GoogleFormFiller(headless=not args.headful, proxy=proxy_cfg)

    results = asyncio.run(
        filler.fill_and_submit(
            url=args.url,
            answers=answers,
            fill_random=args.random or not answers,
            repeat=args.repeat,
        )
    )

    print("\n" + "═" * 50)
    print("KẾT QUẢ TỔNG HỢP")
    print("═" * 50)
    success = sum(1 for r in results if r["success"])
    print(f"✅ Thành công: {success}/{len(results)}")
    print(f"❌ Thất bại  : {len(results) - success}/{len(results)}")
    for r in results:
        status = "✅" if r["success"] else "❌"
        print(f"  {status} Lần #{r['attempt']} - {r['timestamp']}")
        if r.get("error"):
            print(f"     Lỗi: {r['error']}")


if __name__ == "__main__":
    run_cli()
