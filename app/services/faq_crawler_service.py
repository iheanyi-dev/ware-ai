"""
app/services/faq_crawler_service.py

Crawls a React (JS-rendered) site with Playwright, extracts visible text,
splits into overlapping chunks, embeds them with the existing fine-tuned
model (Phase 2/3), and stores them in FaqChunk.

Re-running this for a given source_url REPLACES its old chunks rather
than duplicating them (idempotent, per the working agreement).
"""
"""
app/services/faq_crawler_service.py — add near the top imports
"""
import asyncio
import sys
import concurrent.futures


def _run_crawl_in_new_loop(start_url: str) -> list[dict]:
    """
    Playwright needs subprocess support, which on Windows only the Proactor
    event loop provides — uvicorn's default loop doesn't support it.

    Rather than call the deprecated asyncio.set_event_loop_policy() globally
    (which would also risk changing behavior for the DB driver's loop),
    this creates a Proactor loop directly, scoped to this thread only.
    The main app's event loop is untouched.
    """
    if sys.platform == "win32":
        loop = asyncio.ProactorEventLoop()
    else:
        loop = asyncio.new_event_loop()

    asyncio.set_event_loop(loop)
    try:
        return loop.run_until_complete(crawl_site(start_url))
    finally:
        loop.close()


from urllib.parse import urljoin, urlparse
from urllib import robotparser

from playwright.async_api import async_playwright
from sqlalchemy import delete
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.faq_chunk import FaqChunk
from app.services.embedding_service import embed_texts

MAX_PAGES = 200
DELAY_SECONDS = 60.0
CHUNK_SIZE_WORDS = 300
CHUNK_OVERLAP_WORDS = 50


def chunk_text(text: str, chunk_size: int = CHUNK_SIZE_WORDS, overlap: int = CHUNK_OVERLAP_WORDS) -> list[str]:
    """Splits text into overlapping word-count chunks. Overlap preserves
    context across chunk boundaries so a fact split mid-sentence isn't lost."""
    words = text.split()
    if not words:
        return []
    chunks = []
    start = 0
    while start < len(words):
        end = start + chunk_size
        chunks.append(" ".join(words[start:end]))
        start += chunk_size - overlap
    return chunks


async def _extract_page_text(page) -> tuple[str, str]:
    """Returns (title, visible_text) for the currently loaded page.
    Waits for network idle since React content renders after initial load."""
    await page.wait_for_load_state("networkidle")
    title = await page.title()
    text = await page.inner_text("body")
    return title, "\n".join(line for line in text.splitlines() if line.strip())


async def _get_internal_links(page, base_url: str, domain: str) -> set[str]:
    hrefs = await page.eval_on_selector_all("a[href]", "els => els.map(e => e.href)")
    return {h.split("#")[0] for h in hrefs if urlparse(h).netloc == domain}


async def crawl_site(start_url: str) -> list[dict]:
    """Crawls same-domain pages starting from start_url, returns
    [{url, title, content}, ...] for every page with extractable text."""
    domain = urlparse(start_url).netloc

    rp = robotparser.RobotFileParser()
    rp.set_url(f"{urlparse(start_url).scheme}://{domain}/robots.txt")
    try:
        rp.read()
    except Exception:
        rp = None

    to_visit = {start_url}
    visited = set()
    results = []

    async with async_playwright() as p:
        browser = await p.chromium.launch()
        page = await browser.new_page()

        while to_visit and len(visited) < MAX_PAGES:
            url = to_visit.pop()
            if url in visited or (rp and not rp.can_fetch("*", url)):
                continue
            visited.add(url)

            try:
                await page.goto(url, timeout=15000)
            except Exception:
                continue

            title, text = await _extract_page_text(page)
            if text:
                results.append({"url": url, "title": title, "content": text})

            links = await _get_internal_links(page, url, domain)
            to_visit.update(links - visited)
            await asyncio.sleep(DELAY_SECONDS)

        await browser.close()

    return results


async def crawl_chunk_and_store(start_url: str, db: AsyncSession) -> int:
    """Full pipeline: crawl -> chunk -> embed -> store. Returns chunk count.
    Idempotent per source_url: old chunks for a URL are deleted before new
    ones are inserted, so re-crawling doesn't accumulate duplicates."""
    loop = asyncio.get_event_loop()
    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
        pages = await loop.run_in_executor(executor, _run_crawl_in_new_loop, start_url)
    print(f"Crawled {len(pages)} pages")
    total_chunks = 0
    for page in pages:
        chunks = chunk_text(page["content"])
        if not chunks:
            continue

        # Clear old chunks for this URL first (idempotent re-crawl)
        await db.execute(delete(FaqChunk).where(FaqChunk.source_url == page["url"]))

        embeddings = embed_texts(chunks)  # reuses the fine-tuned model from Phase 2/3
        for i, (chunk, embedding) in enumerate(zip(chunks, embeddings)):
            db.add(FaqChunk(
                source_url=page["url"],
                title=page["title"],
                chunk_index=i,
                content=chunk,
                embedding=embedding,
            ))
        total_chunks += len(chunks)

    await db.commit()
    return total_chunks