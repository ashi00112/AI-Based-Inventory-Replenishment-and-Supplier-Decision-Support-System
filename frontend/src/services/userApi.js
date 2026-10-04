import { API_BASE_URL } from './api';
import { getAuthHeader } from './authApi';

/**
 * Admin User Management API Client.
 * Communicates with protected endpoints under /api/v1/users.
 * Requires ADMIN role.
 */

/**
 * Lists user accounts with optional filtering and pagination.
 *
 * @param {Object} [params]
 * @param {number} [params.skip=0]
 * @param {number} [params.limit=50]
 * @param {string} [params.role]
 * @param {boolean} [params.isActive]
 * @returns {Promise<{success: boolean, data?: {items: Array, total: number}, error?: string}>}
 */
export async function getUsers({ skip = 0, limit = 50, role, isActive } = {}) {
  try {
    let url = `${API_BASE_URL}/users?skip=${skip}&limit=${limit}`;
    if (role) url += `&role=${encodeURIComponent(role)}`;
    if (typeof isActive === 'boolean') url += `&is_active=${isActive}`;

    const response = await fetch(url, {
      method: 'GET',
      headers: {
        'Content-Type': 'application/json',
        ...getAuthHeader(),
      },
    });

    let data;
    try {
      data = await response.json();
    } catch {
      data = null;
    }

    if (response.ok) {
      return { success: true, data };
    }

    return {
      success: false,
      error: data?.detail || `Failed to fetch users (HTTP ${response.status}).`,
    };
  } catch (err) {
    return {
      success: false,
      error: 'Unable to reach the server. Please check connection.',
    };
  }
}

/**
 * Retrieves a single user account by ID.
 *
 * @param {number} userId
 * @returns {Promise<{success: boolean, data?: Object, error?: string}>}
 */
export async function getUser(userId) {
  try {
    const response = await fetch(`${API_BASE_URL}/users/${userId}`, {
      method: 'GET',
      headers: {
        'Content-Type': 'application/json',
        ...getAuthHeader(),
      },
    });

    let data;
    try {
      data = await response.json();
    } catch {
      data = null;
    }

    if (response.ok) {
      return { success: true, data };
    }

    return {
      success: false,
      error: data?.detail || `Failed to load user #${userId}.`,
    };
  } catch (err) {
    return {
      success: false,
      error: 'Network error loading user details.',
    };
  }
}

/**
 * Creates a new user account (Admin-only).
 *
 * @param {Object} userData
 * @param {string} userData.name
 * @param {string} userData.email
 * @param {string} userData.password
 * @param {string} [userData.role='STAFF']
 * @returns {Promise<{success: boolean, data?: Object, error?: string}>}
 */
export async function createUser({ name, email, password, role = 'STAFF' }) {
  try {
    const response = await fetch(`${API_BASE_URL}/users`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        ...getAuthHeader(),
      },
      body: JSON.stringify({
        name: name.trim(),
        email: email.trim().toLowerCase(),
        password,
        role: role.toUpperCase(),
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

    if (response.status === 409) {
      return {
        success: false,
        error: data?.detail || 'An account with this email address already exists.',
      };
    }

    if (response.status === 403) {
      return {
        success: false,
        error: 'Forbidden: Administrative privileges are required to create accounts.',
      };
    }

    if (response.status === 422 && Array.isArray(data?.detail)) {
      const messages = data.detail.map((err) => {
        const field = err.loc ? err.loc[err.loc.length - 1] : 'field';
        return `${field}: ${err.msg}`;
      });
      return { success: false, error: messages.join('; ') };
    }

    return {
      success: false,
      error: data?.detail || `Failed to create user (HTTP ${response.status}).`,
    };
  } catch (err) {
    return {
      success: false,
      error: 'Network error creating user account.',
    };
  }
}

/**
 * Updates an existing user account.
 *
 * @param {number} userId
 * @param {Object} updates
 * @returns {Promise<{success: boolean, data?: Object, error?: string}>}
 */
export async function updateUser(userId, updates) {
  try {
    const response = await fetch(`${API_BASE_URL}/users/${userId}`, {
      method: 'PATCH',
      headers: {
        'Content-Type': 'application/json',
        ...getAuthHeader(),
      },
      body: JSON.stringify(updates),
    });

    let data;
    try {
      data = await response.json();
    } catch {
      data = null;
    }

    if (response.ok) {
      return { success: true, data };
    }

    return {
      success: false,
      error: data?.detail || `Failed to update user #${userId}.`,
    };
  } catch (err) {
    return {
      success: false,
      error: 'Network error updating user.',
    };
  }
}

/**
 * Deactivates a user account (Admin-only).
 *
 * @param {number} userId
 * @returns {Promise<{success: boolean, data?: Object, error?: string}>}
 */
export async function deactivateUser(userId) {
  try {
    const response = await fetch(`${API_BASE_URL}/users/${userId}/deactivate`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        ...getAuthHeader(),
      },
    });

    let data;
    try {
      data = await response.json();
    } catch {
      data = null;
    }

    if (response.ok) {
      return { success: true, data };
    }

    return {
      success: false,
      error: data?.detail || `Failed to deactivate user #${userId}.`,
    };
  } catch (err) {
    return {
      success: false,
      error: 'Network error deactivating user.',
    };
  }
}

/**
 * Reactivates a user account (Admin-only).
 *
 * @param {number} userId
 * @returns {Promise<{success: boolean, data?: Object, error?: string}>}
 */
export async function activateUser(userId) {
  try {
    const response = await fetch(`${API_BASE_URL}/users/${userId}/activate`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        ...getAuthHeader(),
      },
    });

    let data;
    try {
      data = await response.json();
    } catch {
      data = null;
    }

    if (response.ok) {
      return { success: true, data };
    }

    return {
      success: false,
      error: data?.detail || `Failed to activate user #${userId}.`,
    };
  } catch (err) {
    return {
      success: false,
      error: 'Network error activating user.',
    };
  }
}
