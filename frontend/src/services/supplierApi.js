import { API_BASE_URL } from './api';
import { getAuthHeader } from './authApi';

function parseErrorMessage(response, data, fallbackMsg) {
  if (response.status === 409) {
    return data?.detail || 'A supplier with this code already exists.';
  }
  if (response.status === 404) {
    return data?.detail || 'Supplier not found.';
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

export async function getSuppliers({ skip = 0, limit = 100, isActive, search } = {}) {
  try {
    let url = `${API_BASE_URL}/suppliers?skip=${skip}&limit=${limit}`;
    if (typeof isActive === 'boolean') {
      url += `&is_active=${isActive}`;
    }
    if (search) {
      url += `&search=${encodeURIComponent(search)}`;
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

    if (!response.ok) {
      return {
        success: false,
        error: parseErrorMessage(response, data, `Failed to fetch suppliers (HTTP ${response.status}).`),
      };
    }

    return {
      success: true,
      data: Array.isArray(data) ? data : [],
    };
  } catch (err) {
    console.error('[supplierApi] getSuppliers error:', err);
    return {
      success: false,
      error: 'Network error or backend unreachable. Please ensure the backend server is running.',
    };
  }
}

export async function getSupplier(id) {
  try {
    const response = await fetch(`${API_BASE_URL}/suppliers/${id}`, {
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
        error: parseErrorMessage(response, data, `Failed to fetch supplier #${id}.`),
      };
    }

    return {
      success: true,
      data,
    };
  } catch (err) {
    console.error('[supplierApi] getSupplier error:', err);
    return {
      success: false,
      error: 'Network error or backend unreachable.',
    };
  }
}

export async function createSupplier(supplierData) {
  try {
    const response = await fetch(`${API_BASE_URL}/suppliers`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        ...getAuthHeader(),
      },
      body: JSON.stringify(supplierData),
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
        error: parseErrorMessage(response, data, `Failed to create supplier (HTTP ${response.status}).`),
      };
    }

    return {
      success: true,
      data,
    };
  } catch (err) {
    console.error('[supplierApi] createSupplier error:', err);
    return {
      success: false,
      error: 'Network error or backend unreachable.',
    };
  }
}

export async function updateSupplier(id, updateData) {
  try {
    const response = await fetch(`${API_BASE_URL}/suppliers/${id}`, {
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
        error: parseErrorMessage(response, data, `Failed to update supplier #${id}.`),
      };
    }

    return {
      success: true,
      data,
    };
  } catch (err) {
    console.error('[supplierApi] updateSupplier error:', err);
    return {
      success: false,
      error: 'Network error or backend unreachable.',
    };
  }
}

export async function deleteSupplier(id) {
  try {
    const response = await fetch(`${API_BASE_URL}/suppliers/${id}`, {
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
      error: parseErrorMessage(response, data, `Failed to delete supplier #${id}.`),
    };
  } catch (err) {
    console.error('[supplierApi] deleteSupplier error:', err);
    return {
      success: false,
      error: 'Network error or backend unreachable.',
    };
  }
}
