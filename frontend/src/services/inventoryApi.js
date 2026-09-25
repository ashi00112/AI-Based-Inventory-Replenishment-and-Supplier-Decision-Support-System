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
    return data?.detail || 'Inventory record not found.';
  }
  if (response.status === 422) {
    if (Array.isArray(data?.detail)) {
      const messages = data.detail.map((err) => {
        const field = err.loc ? err.loc[err.loc.length - 1] : 'field';
        return `${field}: ${err.msg}`;
      });
      return messages.join('; ');
    }
    return data?.detail || 'Validation error. Please verify stock values.';
  }
  return data?.detail || fallbackMsg;
}

/**
 * Fetches the paginated list of inventory stock records.
 *
 * @param {Object} [params]
 * @param {number} [params.skip=0]
 * @param {number} [params.limit=100]
 * @returns {Promise<{success: boolean, data?: Array, error?: string}>}
 */
export async function getInventory({ skip = 0, limit = 100 } = {}) {
  try {
    const response = await fetch(`${API_BASE_URL}/inventory?skip=${skip}&limit=${limit}`, {
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
      error: parseErrorMessage(response, data, `Failed to load inventory (HTTP ${response.status}).`),
    };
  } catch (err) {
    console.error('[inventoryApi] getInventory error:', err);
    return {
      success: false,
      error: 'Unable to reach the server. Please check your internet connection and verify that the backend server is running.',
    };
  }
}

/**
 * Fetches inventory stock details for a single product by product ID.
 *
 * @param {number|string} productId
 * @returns {Promise<{success: boolean, data?: Object, error?: string}>}
 */
export async function getProductInventory(productId) {
  try {
    const response = await fetch(`${API_BASE_URL}/inventory/products/${productId}`, {
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
      error: parseErrorMessage(response, data, `Failed to load stock for product (HTTP ${response.status}).`),
    };
  } catch (err) {
    console.error('[inventoryApi] getProductInventory error:', err);
    return {
      success: false,
      error: 'Unable to reach the server. Please check your internet connection and verify that the backend server is running.',
    };
  }
}

/**
 * Updates stock levels (on_hand, reserved, incoming) for a product.
 * NOTE: available_stock is never sent to the server as it is derived.
 *
 * @param {number|string} productId
 * @param {Object} stockData
 * @param {number|string} [stockData.on_hand]
 * @param {number|string} [stockData.reserved]
 * @param {number|string} [stockData.incoming]
 * @returns {Promise<{success: boolean, data?: Object, error?: string}>}
 */
export async function updateProductInventory(productId, stockData) {
  try {
    const payload = {};
    if (stockData.on_hand !== undefined && stockData.on_hand !== '') {
      payload.on_hand = parseInt(stockData.on_hand, 10);
    }
    if (stockData.reserved !== undefined && stockData.reserved !== '') {
      payload.reserved = parseInt(stockData.reserved, 10);
    }
    if (stockData.incoming !== undefined && stockData.incoming !== '') {
      payload.incoming = parseInt(stockData.incoming, 10);
    }

    const response = await fetch(`${API_BASE_URL}/inventory/products/${productId}`, {
      method: 'PATCH',
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

    if (response.ok) {
      return { success: true, data };
    }

    return {
      success: false,
      error: parseErrorMessage(response, data, `Failed to update inventory (HTTP ${response.status}).`),
    };
  } catch (err) {
    console.error('[inventoryApi] updateProductInventory error:', err);
    return {
      success: false,
      error: 'Unable to reach the server. Please check your internet connection and verify that the backend server is running.',
    };
  }
}
