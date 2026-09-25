import { API_BASE_URL } from './api';
import { getAccessToken } from './tokenStorage';

/**
 * Registers a new user with the SmartSupply AI backend.
 *
 * @param {Object} userData
 * @param {string} userData.name - User's full name
 * @param {string} userData.email - User's email address
 * @param {string} userData.password - Plain-text password (validated on client and server)
 * @returns {Promise<{success: boolean, data?: Object, error?: string}>}
 */
export async function registerUser({ name, email, password }) {
  try {
    const response = await fetch(`${API_BASE_URL}/auth/register`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({
        name: name.trim(),
        email: email.trim().toLowerCase(),
        password,
      }),
    });

    let data;
    try {
      data = await response.json();
    } catch {
      data = null;
    }

    if (response.status === 201) {
      return { success: true, data };
    }

    // Handle 409 Conflict (Duplicate email)
    if (response.status === 409) {
      return {
        success: false,
        error: data?.detail || 'An account with this email address already exists.',
      };
    }

    // Handle 422 Unprocessable Entity (FastAPI validation errors)
    if (response.status === 422) {
      if (Array.isArray(data?.detail)) {
        // Extract friendly message from Pydantic errors without technical loc dumps
        const messages = data.detail.map((err) => {
          const field = err.loc ? err.loc[err.loc.length - 1] : 'field';
          return `${field}: ${err.msg}`;
        });
        return {
          success: false,
          error: messages.join('; '),
        };
      }
      return {
        success: false,
        error: data?.detail || 'Invalid submission. Please check the entered fields.',
      };
    }

    // Handle unexpected status codes
    return {
      success: false,
      error: data?.detail || `Registration failed (HTTP ${response.status}). Please try again.`,
    };
  } catch {
    // Network or server connectivity errors (never log credentials)
    return {
      success: false,
      error: 'Unable to reach the server. Please check your internet connection and try again.',
    };
  }
}

/**
 * Authenticates an existing user with the SmartSupply AI backend.
 *
 * @param {Object} credentials
 * @param {string} credentials.email - User's email address
 * @param {string} credentials.password - Plain-text password (never logged)
 * @returns {Promise<{success: boolean, data?: {access_token: string, token_type: string}, error?: string}>}
 */
export async function loginUser({ email, password }) {
  try {
    const response = await fetch(`${API_BASE_URL}/auth/login`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({
        email: email.trim().toLowerCase(),
        password,
      }),
    });

    let data;
    try {
      data = await response.json();
    } catch {
      data = null;
    }

    // 200 — Successful authentication
    if (response.status === 200 && data?.access_token) {
      return { success: true, data };
    }

    // 401 — Invalid credentials (generic message; does not reveal account existence)
    if (response.status === 401) {
      return {
        success: false,
        error: data?.detail || 'Invalid email or password.',
      };
    }

    // 403 — Account inactive
    if (response.status === 403) {
      return {
        success: false,
        error: data?.detail || 'Your account is inactive.',
      };
    }

    // 422 — Validation errors from FastAPI/Pydantic
    if (response.status === 422) {
      if (Array.isArray(data?.detail)) {
        const messages = data.detail.map((err) => {
          const field = err.loc ? err.loc[err.loc.length - 1] : 'field';
          return `${field}: ${err.msg}`;
        });
        return {
          success: false,
          error: messages.join('; '),
        };
      }
      return {
        success: false,
        error: data?.detail || 'Invalid submission. Please check the entered fields.',
      };
    }

    // Unexpected status codes
    return {
      success: false,
      error: data?.detail || `Login failed (HTTP ${response.status}). Please try again.`,
    };
  } catch {
    // Network or server connectivity errors (never log credentials or tokens)
    return {
      success: false,
      error: 'Unable to reach the server. Please check your internet connection and try again.',
    };
  }
}

/**
 * Builds an Authorization header using the stored access token.
 *
 * Usage (future protected API calls):
 *   const headers = { ...getAuthHeader(), 'Content-Type': 'application/json' };
 *
 * @returns {{ Authorization: string } | {}}
 */
export function getAuthHeader() {
  const token = getAccessToken();
  if (token) {
    return { Authorization: `Bearer ${token}` };
  }
  return {};
}

/**
 * Fetches the currently authenticated user profile from GET /api/v1/auth/me.
 * Sends the Bearer token retrieved from centralized tokenStorage.
 *
 * @returns {Promise<{success: boolean, data?: Object, error?: string, isUnauthorized?: boolean}>}
 */
export async function getCurrentUser() {
  const token = getAccessToken();
  if (!token) {
    return {
      success: false,
      isUnauthorized: true,
      error: 'No active session token.',
    };
  }

  try {
    const response = await fetch(`${API_BASE_URL}/auth/me`, {
      method: 'GET',
      headers: {
        Authorization: `Bearer ${token}`,
        'Content-Type': 'application/json',
      },
    });

    let data;
    try {
      data = await response.json();
    } catch {
      data = null;
    }

    // 200 OK — Return authenticated user profile
    if (response.status === 200 && data) {
      return { success: true, data };
    }

    // 401 Unauthorized — Token expired, invalid, tampered, or user no longer exists/inactive
    if (response.status === 401) {
      return {
        success: false,
        isUnauthorized: true,
        error: data?.detail || 'Could not validate credentials.',
      };
    }

    // Unexpected HTTP status codes
    return {
      success: false,
      error: data?.detail || `Failed to fetch user session (HTTP ${response.status}).`,
    };
  } catch {
    // Network or server connectivity errors (never log tokens)
    return {
      success: false,
      error: 'Unable to reach the server. Please check your internet connection and try again.',
    };
  }
}

