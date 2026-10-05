import { API_BASE_URL } from './api';
import { getAuthHeader } from './authApi';

function parseErrorMessage(response, data, fallbackMsg) {
  if (response.status === 404) {
    return data?.detail || 'Conversation not found.';
  }
  if (response.status === 400) {
    return data?.detail || 'Invalid message request.';
  }
  if (response.status === 422) {
    if (Array.isArray(data?.detail)) {
      const messages = data.detail.map((err) => {
        const field = err.loc ? err.loc[err.loc.length - 1] : 'field';
        return `${field}: ${err.msg}`;
      });
      return messages.join('; ');
    }
    return data?.detail || 'Validation error.';
  }
  return data?.detail || fallbackMsg;
}

/**
 * Creates a new conversation session.
 */
export async function createConversation(title = null) {
  try {
    const body = title ? { title: title.trim() } : {};
    const response = await fetch(`${API_BASE_URL}/chat/conversations`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        ...getAuthHeader(),
      },
      body: JSON.stringify(body),
    });

    const data = await response.json();
    if (!response.ok) {
      return { success: false, error: parseErrorMessage(response, data, 'Failed to create conversation.') };
    }
    return { success: true, data };
  } catch (err) {
    return { success: false, error: err.message || 'Network error creating conversation.' };
  }
}

/**
 * Fetches user's conversation sessions.
 */
export async function listConversations(limit = 50, offset = 0) {
  try {
    const response = await fetch(`${API_BASE_URL}/chat/conversations?limit=${limit}&offset=${offset}`, {
      method: 'GET',
      headers: {
        ...getAuthHeader(),
      },
    });

    const data = await response.json();
    if (!response.ok) {
      return { success: false, error: parseErrorMessage(response, data, 'Failed to load conversations.') };
    }
    return { success: true, data: Array.isArray(data) ? data : [] };
  } catch (err) {
    return { success: false, error: err.message || 'Network error loading conversations.' };
  }
}

/**
 * Fetches details and messages of a conversation.
 */
export async function getConversation(conversationId) {
  try {
    const response = await fetch(`${API_BASE_URL}/chat/conversations/${conversationId}`, {
      method: 'GET',
      headers: {
        ...getAuthHeader(),
      },
    });

    const data = await response.json();
    if (!response.ok) {
      return { success: false, error: parseErrorMessage(response, data, 'Failed to load messages.') };
    }
    return { success: true, data };
  } catch (err) {
    return { success: false, error: err.message || 'Network error loading conversation.' };
  }
}

/**
 * Deletes a conversation session.
 */
export async function deleteConversation(conversationId) {
  try {
    const response = await fetch(`${API_BASE_URL}/chat/conversations/${conversationId}`, {
      method: 'DELETE',
      headers: {
        ...getAuthHeader(),
      },
    });

    if (!response.ok && response.status !== 204) {
      const data = await response.json().catch(() => null);
      return { success: false, error: parseErrorMessage(response, data, 'Failed to delete conversation.') };
    }
    return { success: true };
  } catch (err) {
    return { success: false, error: err.message || 'Network error deleting conversation.' };
  }
}

/**
 * Sends a message in a conversation.
 */
export async function sendMessage(conversationId, messageText) {
  try {
    const response = await fetch(`${API_BASE_URL}/chat/conversations/${conversationId}/messages`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        ...getAuthHeader(),
      },
      body: JSON.stringify({ message: messageText }),
    });

    const data = await response.json();
    if (!response.ok) {
      return { success: false, error: parseErrorMessage(response, data, 'Failed to send message.') };
    }
    return { success: true, data };
  } catch (err) {
    return { success: false, error: err.message || 'Network error sending message.' };
  }
}
