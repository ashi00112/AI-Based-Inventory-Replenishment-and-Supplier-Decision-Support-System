import { API_BASE_URL } from './api';

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
