import { API_BASE_URL } from './api';
import { getAuthHeader } from './authApi';

function parseErrorMessage(response, data, fallbackMsg) {
  if (response.status === 404) {
    return data?.detail || 'Document or resource not found.';
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

export async function getDocuments({
  skip = 0,
  limit = 100,
  documentType,
  supplierId,
  isActive,
  search,
} = {}) {
  try {
    let url = `${API_BASE_URL}/documents?skip=${skip}&limit=${limit}`;
    if (documentType) {
      url += `&document_type=${encodeURIComponent(documentType)}`;
    }
    if (supplierId) {
      url += `&supplier_id=${supplierId}`;
    }
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
        error: parseErrorMessage(response, data, `Failed to fetch documents (HTTP ${response.status}).`),
      };
    }

    return {
      success: true,
      data: Array.isArray(data) ? data : [],
    };
  } catch (err) {
    return {
      success: false,
      error: err.message || 'Network error while connecting to server.',
    };
  }
}

export async function getDocument(id) {
  try {
    const response = await fetch(`${API_BASE_URL}/documents/${id}`, {
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
        error: parseErrorMessage(response, data, 'Failed to fetch document details.'),
      };
    }

    return {
      success: true,
      data,
    };
  } catch (err) {
    return {
      success: false,
      error: err.message || 'Network error while connecting to server.',
    };
  }
}

export async function uploadDocument(formData) {
  try {
    // Note: Do not set Content-Type header manually; browser will set multipart boundary
    const response = await fetch(`${API_BASE_URL}/documents`, {
      method: 'POST',
      headers: {
        ...getAuthHeader(),
      },
      body: formData,
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
        error: parseErrorMessage(response, data, 'Failed to upload document.'),
      };
    }

    return {
      success: true,
      data,
    };
  } catch (err) {
    return {
      success: false,
      error: err.message || 'Network error while uploading file.',
    };
  }
}

export async function updateDocument(id, payload) {
  try {
    const response = await fetch(`${API_BASE_URL}/documents/${id}`, {
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

    if (!response.ok) {
      return {
        success: false,
        error: parseErrorMessage(response, data, 'Failed to update document.'),
      };
    }

    return {
      success: true,
      data,
    };
  } catch (err) {
    return {
      success: false,
      error: err.message || 'Network error while updating document.',
    };
  }
}

export async function downloadDocument(id, originalFilename) {
  try {
    const response = await fetch(`${API_BASE_URL}/documents/${id}/download`, {
      method: 'GET',
      headers: {
        ...getAuthHeader(),
      },
    });

    if (!response.ok) {
      let errorMsg = `Download failed (HTTP ${response.status}).`;
      try {
        const errData = await response.json();
        errorMsg = errData?.detail || errorMsg;
      } catch {
        // ignore
      }
      return {
        success: false,
        error: errorMsg,
      };
    }

    const blob = await response.blob();
    const downloadUrl = window.URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.href = downloadUrl;
    link.download = originalFilename || `document_${id}.pdf`;
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
    window.URL.revokeObjectURL(downloadUrl);

    return { success: true };
  } catch (err) {
    return {
      success: false,
      error: err.message || 'Failed to download document file.',
    };
  }
}

export async function deleteDocument(id) {
  try {
    const response = await fetch(`${API_BASE_URL}/documents/${id}`, {
      method: 'DELETE',
      headers: {
        ...getAuthHeader(),
      },
    });

    if (!response.ok) {
      let data = null;
      try {
        data = await response.json();
      } catch {
        data = null;
      }
      return {
        success: false,
        error: parseErrorMessage(response, data, 'Failed to delete document.'),
      };
    }

    return {
      success: true,
    };
  } catch (err) {
    return {
      success: false,
      error: err.message || 'Network error while deleting document.',
    };
  }
}
