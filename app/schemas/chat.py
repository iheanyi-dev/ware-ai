# app/schemas/chat.py
"""
Pydantic schemas for the chatbot API.
"""


from pydantic import BaseModel

class ChatRequest(BaseModel):
    message: str

    # Omit or pass null to start a new conversation; pass the id returned
    # from a previous response to continue an existing one.
    conversation_id: int | None = None

    # Optional — lets a logged-in user's messages be associated with their
    # account (visible in ChatConversation.user_id) without requiring it,
    # since anonymous/pre-login visitors can also use the chatbot.
    user_id: int | None = None



class ChatResponse(BaseModel):
    reply: str
    conversation_id: int