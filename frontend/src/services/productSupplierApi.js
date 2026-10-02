import { API_BASE_URL } from './api';
import { getAuthHeader } from './authApi';

function parseErrorMessage(response, data, fallbackMsg) {
  if (response.status === 409) {
    return data?.detail || 'An offer linking this product and supplier already exists.';
  }
  if (response.status === 404) {
    return data?.detail || 'Product-supplier offer not found.';
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

export async function getProductSuppliers({
  productId,
  supplierId,
  isActive,
  skip = 0,
  limit = 100,
} = {}) {
  try {
    let url = `${API_BASE_URL}/product-suppliers?skip=${skip}&limit=${limit}`;
    if (productId) url += `&product_id=${productId}`;
    if (supplierId) url += `&supplier_id=${supplierId}`;
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

    if (!response.ok) {
      return {
        success: false,
        error: parseErrorMessage(
          response,
          data,
          `Failed to fetch product-supplier offers (HTTP ${response.status}).`
        ),
      };
    }

    return {
      success: true,
      data: Array.isArray(data) ? data : [],
    };
  } catch (err) {
    console.error('[productSupplierApi] getProductSuppliers error:', err);
    return {
      success: false,
      error: 'Network error or backend unreachable.',
    };
  }
}

export async function getProductSupplier(id) {
  try {
    const response = await fetch(`${API_BASE_URL}/product-suppliers/${id}`, {
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

    if (!response.ok) {
      return {
        success: false,
        error: parseErrorMessage(
          response,
          data,
          `Failed to fetch offer #${id}.`
        ),
      };
    }

    return {
      success: true,
      data,
    };
  } catch (err) {
    console.error('[productSupplierApi] getProductSupplier error:', err);
    return {
      success: false,
      error: 'Network error or backend unreachable.',
    };
  }
}

export async function createProductSupplier(offerData) {
  try {
    const response = await fetch(`${API_BASE_URL}/product-suppliers`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        ...getAuthHeader(),
      },
      body: JSON.stringify(offerData),
    });

    let data;
    try {
      data = await response.json();
    } catch {
      data = null;
    }

    if (!response.ok) {
      return {
        success: false,
        error: parseErrorMessage(
          response,
          data,
          `Failed to create product-supplier offer (HTTP ${response.status}).`
        ),
      };
    }

    return {
      success: true,
      data,
    };
  } catch (err) {
    console.error('[productSupplierApi] createProductSupplier error:', err);
    return {
      success: false,
      error: 'Network error or backend unreachable.',
    };
  }
}

export async function updateProductSupplier(id, updateData) {
  try {
    const response = await fetch(`${API_BASE_URL}/product-suppliers/${id}`, {
      method: 'PATCH',
      headers: {
        'Content-Type': 'application/json',
        ...getAuthHeader(),
      },
      body: JSON.stringify(updateData),
    });

    let data;
    try {
      data = await response.json();
    } catch {
      data = null;
    }

    if (!response.ok) {
      return {
        success: false,
        error: parseErrorMessage(
          response,
          data,
          `Failed to update offer #${id}.`
        ),
      };
    }

    return {
      success: true,
      data,
    };
  } catch (err) {
    console.error('[productSupplierApi] updateProductSupplier error:', err);
    return {
      success: false,
      error: 'Network error or backend unreachable.',
    };
  }
}

export async function deleteProductSupplier(id) {
  try {
    const response = await fetch(`${API_BASE_URL}/product-suppliers/${id}`, {
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
      error: parseErrorMessage(
        response,
        data,
        `Failed to delete offer #${id}.`
      ),
    };
  } catch (err) {
    console.error('[productSupplierApi] deleteProductSupplier error:', err);
    return {
      success: false,
      error: 'Network error or backend unreachable.',
    };
  }
}
