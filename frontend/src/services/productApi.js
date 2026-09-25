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
  if (response.status === 409) {
    return data?.detail || 'A product with this SKU already exists.';
  }
  if (response.status === 404) {
    return data?.detail || 'Product not found.';
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
 * Fetches a paginated list of catalog products.
 *
 * @param {Object} [params]
 * @param {number} [params.skip=0]
 * @param {number} [params.limit=100]
 * @param {boolean} [params.isActive]
 * @returns {Promise<{success: boolean, data?: Array, error?: string}>}
 */
export async function getProducts({ skip = 0, limit = 100, isActive } = {}) {
  try {
    let url = `${API_BASE_URL}/products?skip=${skip}&limit=${limit}`;
    if (typeof isActive === 'boolean') {
      url += `&is_active=${isActive}`;
    }

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
      error: parseErrorMessage(response, data, `Failed to load products (HTTP ${response.status}).`),
    };
  } catch (err) {
    console.error('[productApi] getProducts error:', err);
    return {
      success: false,
      error: 'Unable to reach the server. Please check your internet connection and verify that the backend server is running.',
    };
  }
}

/**
 * Fetches a single product by its ID.
 *
 * @param {number|string} id
 * @returns {Promise<{success: boolean, data?: Object, error?: string}>}
 */
export async function getProduct(id) {
  try {
    const response = await fetch(`${API_BASE_URL}/products/${id}`, {
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
      error: parseErrorMessage(response, data, `Failed to fetch product (HTTP ${response.status}).`),
    };
  } catch (err) {
    console.error('[productApi] getProduct error:', err);
    return {
      success: false,
      error: 'Unable to reach the server. Please check your internet connection and verify that the backend server is running.',
    };
  }
}

/**
 * Creates a new product in the catalog.
 *
 * @param {Object} productData
 * @param {string} productData.sku
 * @param {string} productData.name
 * @param {string} [productData.category]
 * @param {string} [productData.description]
 * @param {number|string} productData.unit_price
 * @param {number|string} productData.reorder_point
 * @returns {Promise<{success: boolean, data?: Object, error?: string}>}
 */
export async function createProduct(productData) {
  try {
    const response = await fetch(`${API_BASE_URL}/products`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        ...getAuthHeader(),
      },
      body: JSON.stringify({
        sku: (productData.sku || '').trim(),
        name: (productData.name || '').trim(),
        category: productData.category?.trim() || null,
        description: productData.description?.trim() || null,
        unit_price: parseFloat(productData.unit_price) || 0,
        reorder_point: parseInt(productData.reorder_point, 10) || 0,
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

    return {
      success: false,
      error: parseErrorMessage(response, data, `Failed to create product (HTTP ${response.status}).`),
    };
  } catch (err) {
    console.error('[productApi] createProduct network/server error:', err);
    return {
      success: false,
      error: 'Unable to reach the server. Please check your internet connection and verify that the backend server is running.',
    };
  }
}

/**
 * Updates an existing product.
 *
 * @param {number|string} id
 * @param {Object} productData
 * @returns {Promise<{success: boolean, data?: Object, error?: string}>}
 */
export async function updateProduct(id, productData) {
  try {
    const payload = {};
    if (productData.sku !== undefined) payload.sku = (productData.sku || '').trim();
    if (productData.name !== undefined) payload.name = (productData.name || '').trim();
    if (productData.category !== undefined) payload.category = productData.category?.trim() || null;
    if (productData.description !== undefined) payload.description = productData.description?.trim() || null;
    if (productData.unit_price !== undefined) payload.unit_price = parseFloat(productData.unit_price);
    if (productData.reorder_point !== undefined) payload.reorder_point = parseInt(productData.reorder_point, 10);
    if (productData.is_active !== undefined) payload.is_active = Boolean(productData.is_active);

    const response = await fetch(`${API_BASE_URL}/products/${id}`, {
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
      error: parseErrorMessage(response, data, `Failed to update product (HTTP ${response.status}).`),
    };
  } catch (err) {
    console.error('[productApi] updateProduct error:', err);
    return {
      success: false,
      error: 'Unable to reach the server. Please check your internet connection and verify that the backend server is running.',
    };
  }
}

/**
 * Deletes a product from the catalog.
 *
 * @param {number|string} id
 * @returns {Promise<{success: boolean, error?: string}>}
 */
export async function deleteProduct(id) {
  try {
    const response = await fetch(`${API_BASE_URL}/products/${id}`, {
      method: 'DELETE',
      headers: {
        ...getAuthHeader(),
      },
    });

    if (response.status === 204) {
      return { success: true };
    }

    let data;
    try {
      data = await response.json();
    } catch {
      data = null;
    }

    return {
      success: false,
      error: parseErrorMessage(response, data, `Failed to delete product (HTTP ${response.status}).`),
    };
  } catch (err) {
    console.error('[productApi] deleteProduct error:', err);
    return {
      success: false,
      error: 'Unable to reach the server. Please check your internet connection and verify that the backend server is running.',
    };
  }
}
