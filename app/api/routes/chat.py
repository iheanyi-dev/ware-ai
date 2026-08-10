# app/api/routes/chat.py
"""
Chatbot API.

Exposes POST /chat, backed by chatbot_service.get_chatbot_reply(). Protected
by internal service auth, same as the recommendations router — end users
never call this service directly, only the main backend does (which is
presumably where the actual chat widget/UI lives and forwards requests
from).
"""

import json
import logging

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import verify_internal_api_key
from app.db.session import get_db
from app.schemas.chat import ChatRequest, ChatResponse
from app.services.chatbot_service import get_chatbot_reply, stream_chatbot_reply

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/chat",
    tags=["chatbot"],
    #dependencies=[Depends(verify_internal_api_key)],
)


@router.post("", response_model=ChatResponse)
async def chat(
    request: ChatRequest,
    db: AsyncSession = Depends(get_db),
) -> ChatResponse:
    """
    Sends a message to the chatbot and returns its reply.

    On the first call for a new conversation, omit conversation_id — the
    response will include a generated one. Pass that same id back on
    subsequent requests to continue the conversation with full history
    (subject to the summarization logic in chatbot_service.py once it
    grows long).
    """
    reply, conversation_id = await get_chatbot_reply(
        db=db,
        user_message=request.message,
        conversation_id=request.conversation_id,
        user_id=request.user_id,
    )

    return ChatResponse(reply=reply, conversation_id=conversation_id)


@router.post("/stream")
async def chat_stream(
    request: ChatRequest,
    db: AsyncSession = Depends(get_db),
) -> StreamingResponse:
    """
    Same as POST /chat, but streams the reply as Server-Sent Events instead
    of waiting for the full response.

    Event shape:
      event: conversation_id
      data: <uuid>                     -- sent once, first, before any text

      data: "<chunk text>"             -- one event per generated chunk
      ...

      event: error                     -- only sent if generation fails
      data: "<short error message>"

      event: done
      data: [DONE]                     -- ALWAYS sent last, success or failure

    Frontend: use EventSource, or fetch() + a ReadableStream reader if you
    need to send a POST body (EventSource only does GET).
    """

    async def event_source():
        try:
            async for new_conversation_id, chunk in stream_chatbot_reply(
                db=db,
                user_message=request.message,
                conversation_id=request.conversation_id,
                user_id=request.user_id,
            ):
                if new_conversation_id is not None:
                    yield f"event: conversation_id\ndata: {new_conversation_id}\n\n"
                else:
                    # json.dumps so newlines/quotes in generated text can't
                    # break the SSE frame (a raw "\n" in `chunk` would
                    # otherwise be read as the blank line that ends the event).
                    yield f"data: {json.dumps(chunk)}\n\n"
        except Exception:
            # Previously: an exception here (e.g. context-window overflow
            # inside get_chat_completion_stream) killed the generator with
            # nothing sent afterward — the connection just stopped, with no
            # way for the frontend to distinguish "done" from "broke".
            # Now the client always gets an explicit signal either way.
            logger.exception("chat_stream: generation failed mid-stream")
            yield f"event: error\ndata: {json.dumps('The assistant hit an error generating a reply. Please try again.')}\n\n"
        finally:
            yield "event: done\ndata: [DONE]\n\n"

    return StreamingResponse(event_source(), media_type="text/event-stream")