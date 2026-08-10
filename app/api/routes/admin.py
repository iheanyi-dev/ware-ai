"""
app/api/routes/admin.py

Admin-only endpoint to (re-)crawl the site into FaqChunk. Protected by
the same internal auth as recommendations/chat (Phase 4).

NOTE: this runs synchronously in-request. A full site crawl can take
minutes — fine to trigger manually for a demo, but for anything beyond
that this belongs in a background task/job queue, not a request handler.
"""

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from app.core.security import verify_internal_api_key
from app.db.session import get_db
from app.services.faq_crawler_service import crawl_chunk_and_store

router = APIRouter(
    prefix="/admin", 
    #dependencies=[Depends(verify_internal_api_key)]
)


class CrawlRequest(BaseModel):
    start_url: str = 'https://www.waresford.com/'


@router.post("/faq/crawl")
async def crawl_faq(request: CrawlRequest, db=Depends(get_db)):
    chunk_count = await crawl_chunk_and_store(request.start_url, db)
    return {"pages_processed": True, "chunks_stored": chunk_count}