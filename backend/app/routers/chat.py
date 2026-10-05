"""
SmartSupply AI Assistant Chat API Router.
Provides authenticated conversation management and message exchange endpoints.
"""

import logging
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.database.session import get_db
from app.dependencies.auth import get_current_user
from app.models.user import User
from app.schemas.chat import (
    ChatConversationCreate,
    ChatConversationDetail,
    ChatConversationSummary,
    ChatConversationUpdate,
    ChatMessageItem,
    ChatMessageRequest,
    ChatMessageResponse,
)
from app.services.chat_service import ChatService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/chat", tags=["AI Assistant"])


@router.post(
    "/conversations",
    response_model=ChatConversationSummary,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new chat conversation",
)
def create_conversation(
    payload: Optional[ChatConversationCreate] = None,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Initializes a new isolated conversation session for the authenticated user."""
    service = ChatService(db=db, user=current_user)
    title = payload.title if payload else None
    conv = service.create_conversation(title=title)
    return ChatConversationSummary(
        id=conv.id,
        user_id=conv.user_id,
        title=conv.title,
        created_at=conv.created_at,
        updated_at=conv.updated_at,
        message_count=0,
        last_message=None,
    )


@router.get(
    "/conversations",
    response_model=List[ChatConversationSummary],
    summary="List user chat conversations",
)
def list_conversations(
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Retrieves all conversation sessions belonging to the authenticated user, ordered newest first."""
    service = ChatService(db=db, user=current_user)
    return service.list_conversations(limit=limit, offset=offset)


@router.get(
    "/conversations/{conversation_id}",
    response_model=ChatConversationDetail,
    summary="Get conversation details and messages",
)
def get_conversation(
    conversation_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Retrieves conversation details and chronological message history."""
    service = ChatService(db=db, user=current_user)
    conv = service.get_conversation(conversation_id)
    if not conv:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Conversation {conversation_id} not found or access denied.",
        )

    messages = [
        ChatMessageItem(
            id=m.id,
            conversation_id=m.conversation_id,
            role=m.role,
            content=m.content,
            message_metadata=m.message_metadata,
            created_at=m.created_at,
        )
        for m in conv.messages
    ]

    return ChatConversationDetail(
        id=conv.id,
        user_id=conv.user_id,
        title=conv.title,
        created_at=conv.created_at,
        updated_at=conv.updated_at,
        messages=messages,
    )


@router.delete(
    "/conversations/{conversation_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete conversation session",
)
def delete_conversation(
    conversation_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Permanently deletes a conversation session and cascades to its messages."""
    service = ChatService(db=db, user=current_user)
    deleted = service.delete_conversation(conversation_id)
    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Conversation {conversation_id} not found or access denied.",
        )
    return None


@router.patch(
    "/conversations/{conversation_id}",
    response_model=ChatConversationSummary,
    summary="Update conversation title",
)
def update_conversation_title(
    conversation_id: int,
    payload: ChatConversationUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Updates the title of an existing conversation."""
    service = ChatService(db=db, user=current_user)
    conv = service.update_conversation_title(conversation_id, payload.title)
    if not conv:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Conversation {conversation_id} not found or access denied.",
        )
    return ChatConversationSummary(
        id=conv.id,
        user_id=conv.user_id,
        title=conv.title,
        created_at=conv.created_at,
        updated_at=conv.updated_at,
        message_count=len(conv.messages),
        last_message=conv.messages[-1].content[:80] if conv.messages else None,
    )


@router.post(
    "/conversations/{conversation_id}/messages",
    response_model=ChatMessageResponse,
    summary="Send a message to SmartSupply AI Assistant",
)
def send_message(
    conversation_id: int,
    payload: ChatMessageRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Submits a user inquiry to the SmartSupply AI Assistant.
    Orchestrates entity resolution, intent routing, agent capability execution,
    grounded synthesis, and persistence.
    """
    service = ChatService(db=db, user=current_user)
    try:
        response = service.process_user_message(
            conversation_id=conversation_id,
            user_message=payload.message,
        )
        return response
    except ValueError as val_err:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(val_err),
        )
    except Exception as exc:
        logger.exception("Error processing chat message: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to process assistant inquiry.",
        )
