/**
 * Centralized access-token storage for SmartSupply AI.
 *
 * Current storage backend: sessionStorage
 *   - Token is cleared when the browser tab is closed.
 *   - Single storage location — no duplicates in localStorage or cookies.
 *
 * Rules:
 *   - Never log or print the token.
 *   - Never decode the token on the frontend for authorization decisions.
 *   - Never store passwords or email in browser storage.
 */

const TOKEN_KEY = 'smartsupply_access_token';

/**
 * Persist the JWT access token.
 * @param {string} token
 */
export function setAccessToken(token) {
  if (typeof token === 'string' && token.length > 0) {
    sessionStorage.setItem(TOKEN_KEY, token);
  }
}

/**
 * Retrieve the stored JWT access token, or null if absent.
 * @returns {string|null}
 */
export function getAccessToken() {
  return sessionStorage.getItem(TOKEN_KEY);
}

/**
 * Remove the stored JWT access token.
 */
export function removeAccessToken() {
  sessionStorage.removeItem(TOKEN_KEY);
}
