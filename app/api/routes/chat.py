# app/api/routes/chat.py
"""
Chatbot API.

Exposes POST /chat, backed by chatbot_service.get_chatbot_reply(). Protected
by internal service auth, same as the recommendations router — end users
never call this service directly, only the main backend does (which is
presumably where the actual chat widget/UI lives and forwards requests
from).
"""

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import verify_internal_api_key
from app.db.session import get_db
from app.schemas.chat import ChatRequest, ChatResponse
from app.services.chatbot_service import get_chatbot_reply

router = APIRouter(
    prefix="/chat",
    tags=["chatbot"],
    dependencies=[Depends(verify_internal_api_key)],
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