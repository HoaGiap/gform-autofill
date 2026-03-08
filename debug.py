import asyncio
import os
from playwright.async_api import async_playwright

async def main():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()
        print("Navigating...")
        await page.goto("https://docs.google.com/forms/d/e/1FAIpQLSfob46MtFAw7NrStBDX2QBu9JQ1a5iX7yla2i4EWxaLSkOhQQ/viewform?usp=header")
        await page.wait_for_load_state("networkidle")
        
        print("Filling required text...")
        for input_el in await page.query_selector_all('input[type="text"]'):
            if await input_el.is_visible():
                await input_el.fill("Test Name", force=True)

        for input_el in await page.query_selector_all('input[type="email"]'):
            if await input_el.is_visible():
                await input_el.fill("test@gmail.com", force=True)

        radios = await page.query_selector_all('[role="radio"]')
        for radio in radios[:2]:
            if await radio.is_visible():
                await radio.click(force=True)

        print("Clicking Next...")
        next_selectors = '[role="button"][jsname="OCpkoe"], [role="button"][aria-label="Next"], [role="button"][aria-label="Tiếp"]'
        next_btn = await page.query_selector(next_selectors)
        if next_btn:
            print(f"Found next btn. is_disabled? {await next_btn.get_attribute('aria-disabled')}")
            await next_btn.click(force=True)
            await page.wait_for_timeout(3000)
            
            print("--- page 2 buttons ---")
            btns = await page.query_selector_all('[role="button"]')
            for b in btns:
                if await b.is_visible():
                    text = await b.inner_text()
                    if text and any(x in text for x in ["Gửi", "Submit", "Tiếp", "Next"]):
                        print(f"Visible Button Text: {repr(text)}")
                        print(f"HTML: {await b.evaluate('el => el.outerHTML')}")
        else:
            print("No next button found!")
            
        await browser.close()

asyncio.run(main())
