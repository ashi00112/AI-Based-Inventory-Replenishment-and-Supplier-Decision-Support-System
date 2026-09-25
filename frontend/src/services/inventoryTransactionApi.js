import { API_BASE_URL } from './api';
import { getAuthHeader } from './authApi';

/**
 * Normalizes API error messages from FastAPI/Pydantic or server responses.
 *
 * @param {Response} response
 * @param {any} data
 * @param {string} fallbackMsg
 * @returns {string}
 */
function parseErrorMessage(response, data, fallbackMsg) {
  if (response.status === 404) {
    return data?.detail || 'Resource not found.';
  }
  if (response.status === 422) {
    if (Array.isArray(data?.detail)) {
      const messages = data.detail.map((err) => {
        const field = err.loc ? err.loc[err.loc.length - 1] : 'field';
        return `${field}: ${err.msg}`;
      });
      return messages.join('; ');
    }
    return data?.detail || 'Validation error. Please verify the submitted data.';
  }
  return data?.detail || fallbackMsg;
}

/**
 * Records an atomic inventory transaction (SALE, RESTOCK, RETURN, ADJUSTMENT).
 *
 * @param {Object} data
 * @param {number} data.product_id - Product ID
 * @param {string} data.transaction_type - 'sale' | 'restock' | 'return' | 'adjustment'
 * @param {number} data.quantity - Delta quantity
 * @param {string} [data.note] - Optional explanation
 * @returns {Promise<{success: boolean, data?: Object, error?: string}>}
 */
export async function createInventoryTransaction({ product_id, transaction_type, quantity, note }) {
  try {
    const payload = {
      product_id: parseInt(product_id, 10),
      transaction_type: transaction_type.toLowerCase(),
      quantity: parseInt(quantity, 10),
      note: note?.trim() || null,
    };

    const response = await fetch(`${API_BASE_URL}/inventory-transactions`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        ...getAuthHeader(),
      },
      body: JSON.stringify(payload),
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

    return {
      success: false,
      error: parseErrorMessage(
        response,
        data,
        `Failed to record transaction (HTTP ${response.status}).`
      ),
    };
  } catch (err) {
    console.error('[inventoryTransactionApi] createInventoryTransaction error:', err);
    return {
      success: false,
      error: 'Unable to reach the server. Please check your internet connection and verify that the backend server is running.',
    };
  }
}

/**
 * Fetches transaction history with optional filtering.
 *
 * @param {Object} [filters]
 * @param {number} [filters.product_id]
 * @param {string} [filters.transaction_type]
 * @param {number} [filters.skip=0]
 * @param {number} [filters.limit=100]
 * @returns {Promise<{success: boolean, data?: Array, error?: string}>}
 */
export async function getInventoryTransactions(filters = {}) {
  try {
    const params = new URLSearchParams();
    if (filters.product_id) params.append('product_id', filters.product_id);
    if (filters.transaction_type) params.append('transaction_type', filters.transaction_type);
    if (filters.skip !== undefined) params.append('skip', filters.skip);
    if (filters.limit !== undefined) params.append('limit', filters.limit);

    const queryString = params.toString();
    const url = `${API_BASE_URL}/inventory-transactions${queryString ? `?${queryString}` : ''}`;

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
      return { success: true, data: data || [] };
    }

    return {
      success: false,
      error: parseErrorMessage(
        response,
        data,
        `Failed to fetch transaction history (HTTP ${response.status}).`
      ),
    };
  } catch (err) {
    console.error('[inventoryTransactionApi] getInventoryTransactions error:', err);
    return {
      success: false,
      error: 'Unable to reach the server. Please check your internet connection and verify that the backend server is running.',
    };
  }
}

/**
 * Fetches a single transaction by ID.
 *
 * @param {number|string} id
 * @returns {Promise<{success: boolean, data?: Object, error?: string}>}
 */
export async function getInventoryTransaction(id) {
  try {
    const response = await fetch(`${API_BASE_URL}/inventory-transactions/${id}`, {
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
      error: parseErrorMessage(
        response,
        data,
        `Failed to fetch transaction details (HTTP ${response.status}).`
      ),
    };
  } catch (err) {
    console.error('[inventoryTransactionApi] getInventoryTransaction error:', err);
    return {
      success: false,
      error: 'Unable to reach the server. Please check your internet connection and verify that the backend server is running.',
    };
  }
}
