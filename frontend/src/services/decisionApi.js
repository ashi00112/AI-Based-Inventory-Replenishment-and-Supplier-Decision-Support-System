import { API_BASE_URL } from './api';
import { getAuthHeader } from './authApi';

function parseErrorMessage(response, data, fallbackMsg) {
  if (response.status === 404) {
    return data?.detail || 'Decision record or product not found.';
  }
  if (response.status === 409) {
    return data?.detail || 'Decision recommendation state conflict.';
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
 * Generate a new Replenishment and Supplier Decision recommendation.
 *
 * @param {Object} payload
 * @param {number} [payload.productId]
 * @param {string} [payload.sku]
 * @param {number} [payload.forecastHorizonDays=14]
 * @param {string} [payload.urgency]
 * @param {string} [payload.urgencyOverride]
 * @returns {Promise<{success: boolean, data?: import('../types/decision').DecisionRecommendationResponse, error?: string}>}
 */
export async function getRecommendation({
  productId,
  sku,
  forecastHorizonDays = 14,
  urgency,
  urgencyOverride,
}) {
  try {
    const body = {
      forecast_horizon_days: Number(forecastHorizonDays),
    };
    if (productId) body.product_id = Number(productId);
    if (sku) body.sku = sku.trim();
    if (urgencyOverride && urgencyOverride !== 'auto') {
      body.urgency_override = urgencyOverride;
    } else if (urgency && urgency !== 'auto') {
      body.urgency = urgency;
    }

    const response = await fetch(`${API_BASE_URL}/decision/recommend`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        ...getAuthHeader(),
      },
      body: JSON.stringify(body),
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
      error: parseErrorMessage(response, data, `Failed to generate recommendation (HTTP ${response.status}).`),
    };
  } catch (err) {
    return {
      success: false,
      error: err.message || 'Network error contacting decision service.',
    };
  }
}

/**
 * Fetch paginated decision history.
 *
 * @param {Object} [params]
 * @param {number} [params.skip=0]
 * @param {number} [params.limit=50]
 * @param {string} [params.status]
 * @param {number} [params.productId]
 * @returns {Promise<{success: boolean, data?: Object, error?: string}>}
 */
export async function getDecisionHistory({ skip = 0, limit = 50, status, productId } = {}) {
  try {
    const query = new URLSearchParams({ skip, limit });
    if (status) query.append('status', status);
    if (productId) query.append('product_id', productId);

    const response = await fetch(`${API_BASE_URL}/decision/history?${query.toString()}`, {
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
      error: parseErrorMessage(response, data, `Failed to fetch decision history (HTTP ${response.status}).`),
    };
  } catch (err) {
    return {
      success: false,
      error: err.message || 'Network error fetching decision history.',
    };
  }
}

/**
 * Fetch a specific decision recommendation by ID.
 *
 * @param {number} decisionId
 * @returns {Promise<{success: boolean, data?: Object, error?: string}>}
 */
export async function getDecisionById(decisionId) {
  try {
    const response = await fetch(`${API_BASE_URL}/decision/${decisionId}`, {
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
      error: parseErrorMessage(response, data, `Failed to fetch decision details (HTTP ${response.status}).`),
    };
  } catch (err) {
    return {
      success: false,
      error: err.message || 'Network error fetching decision.',
    };
  }
}

/**
 * Human manager approval for a pending replenishment recommendation.
 *
 * @param {number} decisionId
 * @param {Object} [payload]
 * @param {string} [payload.reviewerNotes]
 * @returns {Promise<{success: boolean, data?: Object, error?: string}>}
 */
export async function approveDecision(decisionId, { reviewerNotes } = {}) {
  try {
    const response = await fetch(`${API_BASE_URL}/decision/${decisionId}/approve`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        ...getAuthHeader(),
      },
      body: JSON.stringify({
        status: 'APPROVED',
        reviewer_notes: reviewerNotes || 'Approved by procurement manager.',
      }),
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
      error: parseErrorMessage(response, data, `Failed to approve decision (HTTP ${response.status}).`),
    };
  } catch (err) {
    return {
      success: false,
      error: err.message || 'Network error approving decision.',
    };
  }
}

/**
 * Human manager rejection for a pending recommendation.
 *
 * @param {number} decisionId
 * @param {Object} [payload]
 * @param {string} [payload.rejectionReason]
 * @returns {Promise<{success: boolean, data?: Object, error?: string}>}
 */
export async function rejectDecision(decisionId, { rejectionReason } = {}) {
  try {
    const response = await fetch(`${API_BASE_URL}/decision/${decisionId}/reject`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        ...getAuthHeader(),
      },
      body: JSON.stringify({
        status: 'REJECTED',
        rejection_reason: rejectionReason || 'Rejected by procurement manager.',
      }),
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
      error: parseErrorMessage(response, data, `Failed to reject decision (HTTP ${response.status}).`),
    };
  } catch (err) {
    return {
      success: false,
      error: err.message || 'Network error rejecting decision.',
    };
  }
}
