/**
 * Centralized Client-Side Authentication Manager.
 *
 * Security Principles:
 * - Access Token is stored strictly IN-MEMORY in JS variables.
 * - Refresh Token is managed via HttpOnly secure cookies.
 * - Zero storage in localStorage or sessionStorage (prevents XSS token leakage).
 * - Centralized 401 handling with silent refresh or auto-logout.
 */

class AuthManager {
  constructor() {
    this._accessToken = null;
    this._currentUser = null;
    this._isInitialized = false;
    this._listeners = new Set();
    this._refreshTimer = null;
  }

  get accessToken() {
    return this._accessToken;
  }

  get currentUser() {
    return this._currentUser;
  }

  get isAuthenticated() {
    return !!this._accessToken && !!this._currentUser;
  }

  get role() {
    return this._currentUser ? this._currentUser.role : null;
  }

  isSuperAdmin() {
    return this.role === "SUPER_ADMIN";
  }

  isAdmin() {
    return this.role === "ADMIN" || this.role === "SUPER_ADMIN";
  }

  isOperator() {
    return this.role === "OPERATOR" || this.role === "ADMIN" || this.role === "SUPER_ADMIN";
  }

  isViewer() {
    return !!this.role;
  }

  setSession(accessToken, user, expiresInSeconds = 900) {
    this._accessToken = accessToken;
    this._currentUser = user;
    this._scheduleSilentRefresh(expiresInSeconds);
    this.notify("SESSION_UPDATED");
  }

  clearSession() {
    this._accessToken = null;
    this._currentUser = null;
    if (this._refreshTimer) {
      clearTimeout(this._refreshTimer);
      this._refreshTimer = null;
    }
    this.notify("LOGOUT");
  }

  _scheduleSilentRefresh(expiresInSeconds) {
    if (this._refreshTimer) clearTimeout(this._refreshTimer);
    // Refresh 1 minute before access token expiration
    const refreshDelayMs = Math.max(10000, (expiresInSeconds - 60) * 1000);
    this._refreshTimer = setTimeout(async () => {
      if (this.isAuthenticated) {
        try {
          // Dynamic import to prevent circular dependency
          const { api } = await import("./api.js?v=3.3.0");
          const data = await api.refreshSession();
          if (data && data.access_token) {
            this.setSession(data.access_token, data.user, data.expires_in_seconds);
          }
        } catch (err) {
          console.warn("[AuthManager] Silent token refresh failed:", err);
        }
      }
    }, refreshDelayMs);
  }

  async checkExistingSession() {
    try {
      const { api } = await import("./api.js?v=3.3.0");
      const data = await api.refreshSession();
      if (data && data.access_token) {
        this.setSession(data.access_token, data.user, data.expires_in_seconds);
        this._isInitialized = true;
        return true;
      }
    } catch {
      // No active refresh cookie / anonymous state
    }
    this.clearSession();
    this._isInitialized = true;
    return false;
  }

  subscribe(listener) {
    this._listeners.add(listener);
    return () => this._listeners.delete(listener);
  }

  notify(event) {
    for (const listener of this._listeners) {
      try {
        listener(event, this);
      } catch (e) {
        console.error("[AuthManager] Listener error:", e);
      }
    }
  }
}

export const authManager = new AuthManager();
