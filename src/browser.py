"""
browser.py - Search with Serper and fetch pages with Playwright.
"""

from playwright.sync_api import sync_playwright


class Browser:
    def __init__(self, headless=True):
        self.headless = headless
        self.pw = None
        self.browser = None
        self.page = None

    def launch(self):
        self.pw = sync_playwright().start()
        self.browser = self.pw.chromium.launch(
            headless=self.headless,
            args=["--no-sandbox", "--disable-setuid-sandbox"],
        )
        context = self.browser.new_context(
            viewport={"width": 1280, "height": 800},
            user_agent=(
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/120.0.0.0 Safari/537.36"
            ),
        )
        self.page = context.new_page()
        self.page.set_default_timeout(10_000)
        return self

    def close(self):
        if self.browser:
            self.browser.close()
        if self.pw:
            self.pw.stop()

    def search(self, query):
        import os
        import requests

        key = os.getenv("SERPER_API_KEY")
        if not key:
            raise ValueError("SERPER_API_KEY not set.")

        resp = requests.post(
            "https://google.serper.dev/search",
            headers={"X-API-KEY": key, "Content-Type": "application/json"},
            json={"q": query, "num": 10},
            timeout=15,
        )
        if resp.status_code != 200:
            print(f"    ⚠ Serper API error ({resp.status_code}): {resp.text[:200]}")
            return {"query": query, "results": []}

        results = []
        for i, item in enumerate(resp.json().get("organic", [])[:10]):
            results.append({
                "index": i + 1,
                "title": item.get("title", ""),
                "url": item.get("link", ""),
                "snippet": item.get("snippet", ""),
            })
        return {"query": query, "results": results}

    def navigate(self, url):
        if not url.startswith("http"):
            url = "https://" + url
        self.page.goto(url, wait_until="domcontentloaded", timeout=15_000)
        return {"url": self.page.url, "title": self.page.title()}

    def extract(self, selector="body", max_len=8000):
        try:
            text = self.page.eval_on_selector(selector, """(el) => {
                const clone = el.cloneNode(true);
                clone.querySelectorAll('script, style, noscript, svg, nav, footer, header, [role="navigation"]')
                    .forEach(s => s.remove());
                return clone.innerText?.replace(/\\n{3,}/g, '\\n\\n').trim() || '';
            }""")
            return text[:max_len] + ("\n... [truncated]" if len(text) > max_len else "")
        except Exception:
            return ""

    def fetch_page(self, url):
        try:
            self.navigate(url)
            text = self.extract()
            return {"ok": True, "url": self.page.url, "title": self.page.title(), "text": text}
        except Exception as e:
            return {"ok": False, "url": url, "title": "", "text": "", "error": str(e)}
