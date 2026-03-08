import asyncio
import os
from playwright.async_api import async_playwright

async def main():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()
        await page.goto("https://docs.google.com/forms/d/e/1FAIpQLSfob46MtFAw7NrStBDX2QBu9JQ1a5iX7yla2i4EWxaLSkOhQQ/viewform?usp=header")
        await page.wait_for_load_state("networkidle")
        
        # Fill everything to bypass validation
        for input_el in await page.query_selector_all('input[type="text"]'):
            if await input_el.is_visible(): await input_el.fill("Test Name", force=True)
        for input_el in await page.query_selector_all('input[type="email"]'):
            if await input_el.is_visible(): await input_el.fill("test@gmail.com", force=True)
        
        radios = await page.query_selector_all('[role="radio"]')
        for radio in radios[:3]:
            if await radio.is_visible(): await radio.click(force=True)

        checkboxes = await page.query_selector_all('[role="checkbox"]')
        for cb in checkboxes[:3]:
            if await cb.is_visible(): await cb.click(force=True)
            
        textareas = await page.query_selector_all('textarea')
        for ta in textareas[:3]:
            if await ta.is_visible(): await ta.fill("Test")

        # Click Next
        next_selectors = '[role="button"][jsname="OCpkoe"], [role="button"][aria-label="Next"], [role="button"][aria-label="Tiếp"]'
        next_btn = await page.query_selector(next_selectors)
        if next_btn:
            await next_btn.click(force=True)
            await page.wait_for_timeout(3000)
            
            # Save the full HTML of page 2 to a file for inspection
            html = await page.content()
            with open("page2_dump.html", "w", encoding="utf-8") as f:
                f.write(html)
        else:
            print("Next button not found!")
            
        await browser.close()

asyncio.run(main())
