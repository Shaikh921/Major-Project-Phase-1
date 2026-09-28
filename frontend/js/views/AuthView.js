/**
 * Authentication View Component.
 *
 * Implements SRE Command Center themed portal for:
 * - Administrator & User Sign In
 * - Forgot Password request
 * - Password Reset execution
 * - User Email Verification
 * - Prospective Admin Access Request submission
 * - Admin Request Email Verification (#verify-admin-request)
 * - Approved Admin Account Activation (#activate-admin)
 *
 * Adheres strictly to the Point 1 SVG Icon system and design tokens.
 */

import { api } from "../api.js?v=3.3.0";
import { authManager } from "../auth.js?v=3.3.0";
import { escapeHtml } from "../sanitizer.js?v=3.3.0";
import { renderIcon } from "../components/Icons.js?v=3.3.0";

export function renderAuthView(container, initialMode = "login", tokenParam = "") {
  let mode = initialMode;
  let resetToken = tokenParam;
  let verifyToken = tokenParam;
  let requestVerifyToken = tokenParam;
  let activationToken = tokenParam;

  // Check URL hash for direct action links
  const hash = window.location.hash || "";
  if (hash.startsWith("#verify-email")) {
    mode = "verify";
    const params = new URLSearchParams(hash.split("?")[1] || "");
    if (params.get("token")) verifyToken = params.get("token");
  } else if (hash.startsWith("#reset-password")) {
    mode = "reset";
    const params = new URLSearchParams(hash.split("?")[1] || "");
    if (params.get("token")) resetToken = params.get("token");
  } else if (hash.startsWith("#verify-admin-request")) {
    mode = "verify-request";
    const params = new URLSearchParams(hash.split("?")[1] || "");
    if (params.get("token")) requestVerifyToken = params.get("token");
  } else if (hash.startsWith("#activate-admin")) {
    mode = "activate-admin";
    const params = new URLSearchParams(hash.split("?")[1] || "");
    if (params.get("token")) activationToken = params.get("token");
  }

  function render() {
    container.innerHTML = `
      <div style="display: flex; align-items: center; justify-content: center; min-height: calc(100vh - 120px); padding: 24px;">
        <div class="panel" style="width: 100%; max-width: 480px; border: 1px solid var(--border-default); box-shadow: 0 8px 32px rgba(0, 0, 0, 0.45);">
          <!-- Header Branding -->
          <div style="text-align: center; padding: 28px 24px 20px; border-bottom: 1px solid var(--border-subtle);">
            <div style="display: inline-flex; align-items: center; justify-content: center; width: 46px; height: 46px; border-radius: 8px; background: rgba(59, 130, 246, 0.12); color: var(--status-info); margin-bottom: 12px; border: 1px solid var(--border-highlight);">
              ${renderIcon("shield-check", { size: "lg" })}
            </div>
            <h2 style="font-size: 18px; font-weight: 700; letter-spacing: -0.01em; margin: 0 0 4px; color: var(--text-primary);">
              CloudOps Intel
            </h2>
            <p style="font-size: 12px; color: var(--text-muted); margin: 0;">
              SRE & SOC Operations Authentication Portal
            </p>
          </div>

          <!-- Tab Selector -->
          <div style="display: flex; border-bottom: 1px solid var(--border-subtle); background: var(--bg-surface-elevated);">
            <button class="btn btn-sm ${mode === 'login' ? 'btn-primary' : ''}" id="auth-tab-login" style="flex: 1; border-radius: 0; border: none; justify-content: center; padding: 10px; font-size: 11px; font-weight: 600;">
              ${renderIcon("lock", { size: "xs" })} Sign In
            </button>
            <button class="btn btn-sm ${mode === 'request-access' ? 'btn-primary' : ''}" id="auth-tab-request" style="flex: 1; border-radius: 0; border: none; justify-content: center; padding: 10px; font-size: 11px; font-weight: 600;">
              ${renderIcon("user-plus", { size: "xs" })} Request Access
            </button>
            <button class="btn btn-sm ${mode === 'forgot' ? 'btn-primary' : ''}" id="auth-tab-forgot" style="flex: 1; border-radius: 0; border: none; justify-content: center; padding: 10px; font-size: 11px; font-weight: 600;">
              ${renderIcon("key", { size: "xs" })} Recovery
            </button>
            <button class="btn btn-sm ${mode === 'verify' ? 'btn-primary' : ''}" id="auth-tab-verify" style="flex: 1; border-radius: 0; border: none; justify-content: center; padding: 10px; font-size: 11px; font-weight: 600;">
              ${renderIcon("check-circle-2", { size: "xs" })} Verify
            </button>
          </div>

          <!-- Body Content Area -->
          <div style="padding: 24px;" id="auth-form-container">
            ${mode === "login" ? renderLoginForm() : ""}
            ${mode === "request-access" ? renderRequestAccessForm() : ""}
            ${mode === "forgot" ? renderForgotForm() : ""}
            ${mode === "reset" ? renderResetForm(resetToken) : ""}
            ${mode === "verify" ? renderVerifyForm(verifyToken) : ""}
            ${mode === "verify-request" ? renderVerifyRequestForm(requestVerifyToken) : ""}
            ${mode === "activate-admin" ? renderActivateAdminForm(activationToken) : ""}
          </div>
        </div>
      </div>
    `;

    bindTabEvents();
    bindFormActions();
  }

  function renderLoginForm() {
    return `
      <form id="login-form" style="display: flex; flex-direction: column; gap: 16px;">
        <div id="auth-alert" style="display: none;"></div>

        <div>
          <label style="display: block; font-size: 11px; font-weight: 600; color: var(--text-secondary); margin-bottom: 6px; letter-spacing: 0.04em;">
            ADMIN / OPERATOR EMAIL
          </label>
          <div style="position: relative;">
            <input type="email" id="login-email" class="input-control" required placeholder="admin@ops.local" style="width: 100%; padding-left: 32px;" autocomplete="username">
            <span style="position: absolute; left: 10px; top: 9px; color: var(--text-muted); pointer-events: none;">
              ${renderIcon("user", { size: "xs" })}
            </span>
          </div>
        </div>

        <div>
          <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 6px;">
            <label style="font-size: 11px; font-weight: 600; color: var(--text-secondary); letter-spacing: 0.04em;">
              PASSWORD
            </label>
            <a href="javascript:void(0)" id="link-goto-forgot" style="font-size: 11px; color: var(--status-info); text-decoration: none;">
              Forgot password?
            </a>
          </div>
          <div style="position: relative;">
            <input type="password" id="login-password" class="input-control" required placeholder="••••••••" style="width: 100%; padding-left: 32px; padding-right: 36px;" autocomplete="current-password">
            <span style="position: absolute; left: 10px; top: 9px; color: var(--text-muted); pointer-events: none;">
              ${renderIcon("lock", { size: "xs" })}
            </span>
            <button type="button" id="toggle-password-btn" style="position: absolute; right: 8px; top: 7px; background: transparent; border: none; color: var(--text-muted); cursor: pointer; padding: 2px;">
              ${renderIcon("eye", { size: "xs" })}
            </button>
          </div>
        </div>

        <button type="submit" class="btn btn-primary" id="login-submit-btn" style="width: 100%; justify-content: center; padding: 10px; font-weight: 600; margin-top: 4px;">
          ${renderIcon("log-in", { size: "sm" })} Sign In to Command Center
        </button>

        <div style="text-align: center; margin-top: 4px;">
          <a href="javascript:void(0)" id="link-goto-request" style="font-size: 11.5px; color: var(--text-muted); text-decoration: none;">
            Need Administrator Access? <span style="color: var(--status-info);">Request access</span>
          </a>
        </div>
      </form>
    `;
  }

  function renderRequestAccessForm() {
    return `
      <form id="request-access-form" style="display: flex; flex-direction: column; gap: 14px;">
        <div id="auth-alert" style="display: none;"></div>

        <p style="font-size: 11.5px; color: var(--text-secondary); line-height: 1.45; margin: 0;">
          Submit your details to request an operational Administrator account. Requests require email verification followed by Super Admin review.
        </p>

        <div>
          <label style="display: block; font-size: 11px; font-weight: 600; color: var(--text-secondary); margin-bottom: 4px; letter-spacing: 0.04em;">
            FULL NAME
          </label>
          <input type="text" id="req-fullname" class="input-control" required placeholder="Alex Mercer" style="width: 100%;">
        </div>

        <div>
          <label style="display: block; font-size: 11px; font-weight: 600; color: var(--text-secondary); margin-bottom: 4px; letter-spacing: 0.04em;">
            EMAIL ADDRESS
          </label>
          <input type="email" id="req-email" class="input-control" required placeholder="alex@ops.local" style="width: 100%;">
        </div>

        <div>
          <label style="display: block; font-size: 11px; font-weight: 600; color: var(--text-secondary); margin-bottom: 4px; letter-spacing: 0.04em;">
            DEPARTMENT / ORGANIZATION (OPTIONAL)
          </label>
          <input type="text" id="req-org" class="input-control" placeholder="Site Reliability Engineering" style="width: 100%;">
        </div>

        <div>
          <label style="display: block; font-size: 11px; font-weight: 600; color: var(--text-secondary); margin-bottom: 4px; letter-spacing: 0.04em;">
            REASON FOR ADMIN ACCESS (OPTIONAL)
          </label>
          <textarea id="req-reason" class="input-control" rows="2" placeholder="Explain your operational monitoring or incident response responsibilities" style="width: 100%; resize: vertical;"></textarea>
        </div>

        <button type="submit" class="btn btn-primary" id="request-submit-btn" style="width: 100%; justify-content: center; padding: 10px; font-weight: 600; margin-top: 4px;">
          ${renderIcon("send", { size: "sm" })} Submit Access Request
        </button>

        <div style="text-align: center; margin-top: 4px;">
          <a href="javascript:void(0)" id="link-req-back-login" style="font-size: 11.5px; color: var(--text-muted); text-decoration: none;">
            ${renderIcon("arrow-left", { size: "xs" })} Return to Sign In
          </a>
        </div>
      </form>
    `;
  }

  function renderForgotForm() {
    return `
      <form id="forgot-form" style="display: flex; flex-direction: column; gap: 16px;">
        <div id="auth-alert" style="display: none;"></div>

        <p style="font-size: 12px; color: var(--text-secondary); line-height: 1.5; margin: 0;">
          Enter your registered email address. If your account exists, a secure time-limited password recovery link will be dispatched.
        </p>

        <div>
          <label style="display: block; font-size: 11px; font-weight: 600; color: var(--text-secondary); margin-bottom: 6px; letter-spacing: 0.04em;">
            ACCOUNT EMAIL
          </label>
          <div style="position: relative;">
            <input type="email" id="forgot-email" class="input-control" required placeholder="user@ops.local" style="width: 100%; padding-left: 32px;">
            <span style="position: absolute; left: 10px; top: 9px; color: var(--text-muted); pointer-events: none;">
              ${renderIcon("mail", { size: "xs" })}
            </span>
          </div>
        </div>

        <button type="submit" class="btn btn-primary" id="forgot-submit-btn" style="width: 100%; justify-content: center; padding: 10px; font-weight: 600;">
          ${renderIcon("send", { size: "sm" })} Send Recovery Instructions
        </button>

        <div style="text-align: center; margin-top: 4px;">
          <a href="javascript:void(0)" id="link-back-login" style="font-size: 11.5px; color: var(--text-muted); text-decoration: none;">
            ${renderIcon("arrow-left", { size: "xs" })} Return to Sign In
          </a>
        </div>
      </form>
    `;
  }

  function renderResetForm(token) {
    return `
      <form id="reset-form" style="display: flex; flex-direction: column; gap: 16px;">
        <div id="auth-alert" style="display: none;"></div>

        <p style="font-size: 12px; color: var(--text-secondary); line-height: 1.5; margin: 0;">
          Enter your single-use reset token and choose a new high-security password (minimum 8 characters).
        </p>

        <div>
          <label style="display: block; font-size: 11px; font-weight: 600; color: var(--text-secondary); margin-bottom: 6px; letter-spacing: 0.04em;">
            RESET TOKEN
          </label>
          <input type="text" id="reset-token" class="input-control mono" required value="${escapeHtml(token)}" placeholder="Paste reset token here" style="width: 100%;">
        </div>

        <div>
          <label style="display: block; font-size: 11px; font-weight: 600; color: var(--text-secondary); margin-bottom: 6px; letter-spacing: 0.04em;">
            NEW PASSWORD (MIN 8 CHARACTERS)
          </label>
          <input type="password" id="reset-new-password" class="input-control" required minlength="8" placeholder="••••••••" style="width: 100%;">
        </div>

        <div>
          <label style="display: block; font-size: 11px; font-weight: 600; color: var(--text-secondary); margin-bottom: 6px; letter-spacing: 0.04em;">
            CONFIRM NEW PASSWORD
          </label>
          <input type="password" id="reset-confirm-password" class="input-control" required minlength="8" placeholder="••••••••" style="width: 100%;">
        </div>

        <button type="submit" class="btn btn-primary" id="reset-submit-btn" style="width: 100%; justify-content: center; padding: 10px; font-weight: 600;">
          ${renderIcon("shield-check", { size: "sm" })} Set New Password
        </button>

        <div style="text-align: center; margin-top: 4px;">
          <a href="javascript:void(0)" id="link-reset-back-login" style="font-size: 11.5px; color: var(--text-muted); text-decoration: none;">
            ${renderIcon("arrow-left", { size: "xs" })} Return to Sign In
          </a>
        </div>
      </form>
    `;
  }

  function renderVerifyForm(token) {
    return `
      <form id="verify-form" style="display: flex; flex-direction: column; gap: 16px;">
        <div id="auth-alert" style="display: none;"></div>

        <p style="font-size: 12px; color: var(--text-secondary); line-height: 1.5; margin: 0;">
          Enter or confirm the verification token received during user account onboarding to activate your platform access.
        </p>

        <div>
          <label style="display: block; font-size: 11px; font-weight: 600; color: var(--text-secondary); margin-bottom: 6px; letter-spacing: 0.04em;">
            EMAIL VERIFICATION TOKEN
          </label>
          <input type="text" id="verify-token-input" class="input-control mono" required value="${escapeHtml(token)}" placeholder="Paste verification token" style="width: 100%;">
        </div>

        <button type="submit" class="btn btn-primary" id="verify-submit-btn" style="width: 100%; justify-content: center; padding: 10px; font-weight: 600;">
          ${renderIcon("check-circle-2", { size: "sm" })} Verify Account Email
        </button>

        <div style="text-align: center; margin-top: 4px;">
          <a href="javascript:void(0)" id="link-verify-back-login" style="font-size: 11.5px; color: var(--text-muted); text-decoration: none;">
            ${renderIcon("arrow-left", { size: "xs" })} Return to Sign In
          </a>
        </div>
      </form>
    `;
  }

  function renderVerifyRequestForm(token) {
    return `
      <form id="verify-req-form" style="display: flex; flex-direction: column; gap: 16px;">
        <div id="auth-alert" style="display: none;"></div>

        <p style="font-size: 12px; color: var(--text-secondary); line-height: 1.5; margin: 0;">
          Confirm the verification token for your Admin Access Request to forward it to the Super Admin approval queue.
        </p>

        <div>
          <label style="display: block; font-size: 11px; font-weight: 600; color: var(--text-secondary); margin-bottom: 6px; letter-spacing: 0.04em;">
            REQUEST VERIFICATION TOKEN
          </label>
          <input type="text" id="verify-req-token-input" class="input-control mono" required value="${escapeHtml(token)}" placeholder="Paste token here" style="width: 100%;">
        </div>

        <button type="submit" class="btn btn-primary" id="verify-req-submit-btn" style="width: 100%; justify-content: center; padding: 10px; font-weight: 600;">
          ${renderIcon("check-circle-2", { size: "sm" })} Verify Request Email
        </button>

        <div style="text-align: center; margin-top: 4px;">
          <a href="javascript:void(0)" id="link-verify-req-back-login" style="font-size: 11.5px; color: var(--text-muted); text-decoration: none;">
            ${renderIcon("arrow-left", { size: "xs" })} Return to Sign In
          </a>
        </div>
      </form>
    `;
  }

  function renderActivateAdminForm(token) {
    return `
      <form id="activate-admin-form" style="display: flex; flex-direction: column; gap: 16px;">
        <div id="auth-alert" style="display: none;"></div>

        <div style="padding: 12px; border-radius: var(--radius-sm); background: rgba(59, 130, 246, 0.08); border: 1px solid var(--border-highlight); margin-bottom: 4px;">
          <div style="font-size: 12px; font-weight: 600; color: var(--status-info); margin-bottom: 2px;">
            ${renderIcon("shield-check", { size: "xs" })} Request Approved
          </div>
          <p style="font-size: 11.5px; color: var(--text-secondary); margin: 0;">
            Your Administrator access request was approved. Set your initial high-security password to activate your account.
          </p>
        </div>

        <div>
          <label style="display: block; font-size: 11px; font-weight: 600; color: var(--text-secondary); margin-bottom: 6px; letter-spacing: 0.04em;">
            ACTIVATION TOKEN
          </label>
          <input type="text" id="activate-token-input" class="input-control mono" required value="${escapeHtml(token)}" placeholder="Paste activation token" style="width: 100%;">
        </div>

        <div>
          <label style="display: block; font-size: 11px; font-weight: 600; color: var(--text-secondary); margin-bottom: 6px; letter-spacing: 0.04em;">
            SET PASSWORD (MIN 8 CHARACTERS)
          </label>
          <input type="password" id="activate-password" class="input-control" required minlength="8" placeholder="••••••••" style="width: 100%;">
        </div>

        <div>
          <label style="display: block; font-size: 11px; font-weight: 600; color: var(--text-secondary); margin-bottom: 6px; letter-spacing: 0.04em;">
            CONFIRM PASSWORD
          </label>
          <input type="password" id="activate-confirm-password" class="input-control" required minlength="8" placeholder="••••••••" style="width: 100%;">
        </div>

        <button type="submit" class="btn btn-primary" id="activate-submit-btn" style="width: 100%; justify-content: center; padding: 10px; font-weight: 600;">
          ${renderIcon("check-circle-2", { size: "sm" })} Activate Administrator Account
        </button>

        <div style="text-align: center; margin-top: 4px;">
          <a href="javascript:void(0)" id="link-activate-back-login" style="font-size: 11.5px; color: var(--text-muted); text-decoration: none;">
            ${renderIcon("arrow-left", { size: "xs" })} Return to Sign In
          </a>
        </div>
      </form>
    `;
  }

  function showAlert(message, type = "error") {
    const alertBox = document.getElementById("auth-alert");
    if (!alertBox) return;

    const isSuccess = type === "success";
    alertBox.style.display = "block";
    alertBox.style.padding = "10px 12px";
    alertBox.style.borderRadius = "var(--radius-sm)";
    alertBox.style.fontSize = "11.5px";
    alertBox.style.lineHeight = "1.4";
    alertBox.style.marginBottom = "12px";

    if (isSuccess) {
      alertBox.style.background = "var(--status-healthy-bg)";
      alertBox.style.border = "1px solid var(--status-healthy-border)";
      alertBox.style.color = "var(--status-healthy)";
      alertBox.innerHTML = `${renderIcon("check-circle-2", { size: "xs" })} ${escapeHtml(message)}`;
    } else {
      alertBox.style.background = "var(--status-critical-bg)";
      alertBox.style.border = "1px solid var(--status-critical-border)";
      alertBox.style.color = "var(--status-critical)";
      alertBox.innerHTML = `${renderIcon("triangle-alert", { size: "xs" })} ${escapeHtml(message)}`;
    }
  }

  function bindTabEvents() {
    const tabLogin = document.getElementById("auth-tab-login");
    const tabRequest = document.getElementById("auth-tab-request");
    const tabForgot = document.getElementById("auth-tab-forgot");
    const tabVerify = document.getElementById("auth-tab-verify");

    if (tabLogin) tabLogin.onclick = () => { mode = "login"; render(); };
    if (tabRequest) tabRequest.onclick = () => { mode = "request-access"; render(); };
    if (tabForgot) tabForgot.onclick = () => { mode = "forgot"; render(); };
    if (tabVerify) tabVerify.onclick = () => { mode = "verify"; render(); };

    const gotoForgot = document.getElementById("link-goto-forgot");
    if (gotoForgot) gotoForgot.onclick = () => { mode = "forgot"; render(); };

    const gotoRequest = document.getElementById("link-goto-request");
    if (gotoRequest) gotoRequest.onclick = () => { mode = "request-access"; render(); };

    const reqBackLogin = document.getElementById("link-req-back-login");
    if (reqBackLogin) reqBackLogin.onclick = () => { mode = "login"; render(); };

    const backLogin = document.getElementById("link-back-login");
    if (backLogin) backLogin.onclick = () => { mode = "login"; render(); };

    const resetBackLogin = document.getElementById("link-reset-back-login");
    if (resetBackLogin) resetBackLogin.onclick = () => { mode = "login"; render(); };

    const verifyBackLogin = document.getElementById("link-verify-back-login");
    if (verifyBackLogin) verifyBackLogin.onclick = () => { mode = "login"; render(); };

    const verifyReqBackLogin = document.getElementById("link-verify-req-back-login");
    if (verifyReqBackLogin) verifyReqBackLogin.onclick = () => { mode = "login"; render(); };

    const activateBackLogin = document.getElementById("link-activate-back-login");
    if (activateBackLogin) activateBackLogin.onclick = () => { mode = "login"; render(); };

    const togglePwdBtn = document.getElementById("toggle-password-btn");
    const pwdInput = document.getElementById("login-password");
    if (togglePwdBtn && pwdInput) {
      togglePwdBtn.onclick = () => {
        const isPwd = pwdInput.type === "password";
        pwdInput.type = isPwd ? "text" : "password";
        togglePwdBtn.innerHTML = isPwd ? renderIcon("eye-off", { size: "xs" }) : renderIcon("eye", { size: "xs" });
      };
    }
  }

  function bindFormActions() {
    // 1. Sign In
    const loginForm = document.getElementById("login-form");
    if (loginForm) {
      loginForm.onsubmit = async (e) => {
        e.preventDefault();
        const email = document.getElementById("login-email").value.trim();
        const password = document.getElementById("login-password").value;
        const submitBtn = document.getElementById("login-submit-btn");

        submitBtn.disabled = true;
        submitBtn.innerHTML = `${renderIcon("loader", { size: "xs", className: "icon-spin" })} Authenticating...`;

        try {
          const res = await api.login(email, password);
          authManager.setSession(res.access_token, res.user, res.expires_in_seconds);
        } catch (err) {
          showAlert(err.message, "error");
          submitBtn.disabled = false;
          submitBtn.innerHTML = `${renderIcon("log-in", { size: "sm" })} Sign In to Command Center`;
        }
      };
    }

    // 2. Request Admin Access
    const reqForm = document.getElementById("request-access-form");
    if (reqForm) {
      reqForm.onsubmit = async (e) => {
        e.preventDefault();
        const fullName = document.getElementById("req-fullname").value.trim();
        const email = document.getElementById("req-email").value.trim();
        const organization = document.getElementById("req-org").value.trim();
        const reason = document.getElementById("req-reason").value.trim();
        const submitBtn = document.getElementById("request-submit-btn");

        submitBtn.disabled = true;
        submitBtn.innerHTML = `${renderIcon("loader", { size: "xs", className: "icon-spin" })} Submitting...`;

        try {
          await api.requestAdminAccess({
            full_name: fullName,
            email,
            organization: organization || null,
            reason: reason || null,
          });
          showAlert("Your request has been submitted. Please verify your email address to continue.", "success");
          submitBtn.disabled = false;
          submitBtn.innerHTML = `${renderIcon("check-circle-2", { size: "sm" })} Request Submitted`;
        } catch (err) {
          showAlert(err.message, "error");
          submitBtn.disabled = false;
          submitBtn.innerHTML = `${renderIcon("send", { size: "sm" })} Submit Access Request`;
        }
      };
    }

    // 3. Verify Admin Request Email
    const verifyReqForm = document.getElementById("verify-req-form");
    if (verifyReqForm) {
      verifyReqForm.onsubmit = async (e) => {
        e.preventDefault();
        const token = document.getElementById("verify-req-token-input").value.trim();
        const submitBtn = document.getElementById("verify-req-submit-btn");

        submitBtn.disabled = true;
        submitBtn.innerHTML = `${renderIcon("loader", { size: "xs", className: "icon-spin" })} Verifying...`;

        try {
          const res = await api.verifyAdminRequest(token);
          showAlert(`${res.message} Returning to sign in in 3 seconds...`, "success");
          submitBtn.disabled = false;
          submitBtn.innerHTML = `${renderIcon("check-circle-2", { size: "sm" })} Verified`;
          setTimeout(() => {
            mode = "login";
            window.location.hash = "";
            render();
          }, 3000);
        } catch (err) {
          showAlert(err.message, "error");
          submitBtn.disabled = false;
          submitBtn.innerHTML = `${renderIcon("check-circle-2", { size: "sm" })} Verify Request Email`;
        }
      };
    }

    // 4. Activate Admin Account
    const activateForm = document.getElementById("activate-admin-form");
    if (activateForm) {
      activateForm.onsubmit = async (e) => {
        e.preventDefault();
        const token = document.getElementById("activate-token-input").value.trim();
        const password = document.getElementById("activate-password").value;
        const confirmPassword = document.getElementById("activate-confirm-password").value;
        const submitBtn = document.getElementById("activate-submit-btn");

        if (password !== confirmPassword) {
          showAlert("Passwords do not match.", "error");
          return;
        }

        submitBtn.disabled = true;
        submitBtn.innerHTML = `${renderIcon("loader", { size: "xs", className: "icon-spin" })} Activating...`;

        try {
          const res = await api.activateAdminAccount(token, password);
          showAlert(`${res.message} Redirecting to Sign In in 2 seconds...`, "success");
          setTimeout(() => {
            mode = "login";
            window.location.hash = "";
            render();
          }, 2000);
        } catch (err) {
          showAlert(err.message, "error");
          submitBtn.disabled = false;
          submitBtn.innerHTML = `${renderIcon("check-circle-2", { size: "sm" })} Activate Administrator Account`;
        }
      };
    }

    // 5. Forgot Password
    const forgotForm = document.getElementById("forgot-form");
    if (forgotForm) {
      forgotForm.onsubmit = async (e) => {
        e.preventDefault();
        const email = document.getElementById("forgot-email").value.trim();
        const submitBtn = document.getElementById("forgot-submit-btn");

        submitBtn.disabled = true;
        submitBtn.innerHTML = `${renderIcon("loader", { size: "xs", className: "icon-spin" })} Dispatching...`;

        try {
          const res = await api.forgotPassword(email);
          showAlert(res.message, "success");
          submitBtn.disabled = false;
          submitBtn.innerHTML = `${renderIcon("send", { size: "sm" })} Send Recovery Instructions`;
        } catch (err) {
          showAlert(err.message, "error");
          submitBtn.disabled = false;
          submitBtn.innerHTML = `${renderIcon("send", { size: "sm" })} Send Recovery Instructions`;
        }
      };
    }

    // 6. Reset Password
    const resetForm = document.getElementById("reset-form");
    if (resetForm) {
      resetForm.onsubmit = async (e) => {
        e.preventDefault();
        const token = document.getElementById("reset-token").value.trim();
        const newPassword = document.getElementById("reset-new-password").value;
        const confirmPassword = document.getElementById("reset-confirm-password").value;
        const submitBtn = document.getElementById("reset-submit-btn");

        if (newPassword !== confirmPassword) {
          showAlert("New passwords do not match.", "error");
          return;
        }

        submitBtn.disabled = true;
        submitBtn.innerHTML = `${renderIcon("loader", { size: "xs", className: "icon-spin" })} Updating Password...`;

        try {
          const res = await api.resetPassword(token, newPassword);
          showAlert(`${res.message} Redirecting to Sign In in 2 seconds...`, "success");
          setTimeout(() => {
            mode = "login";
            window.location.hash = "";
            render();
          }, 2000);
        } catch (err) {
          showAlert(err.message, "error");
          submitBtn.disabled = false;
          submitBtn.innerHTML = `${renderIcon("shield-check", { size: "sm" })} Set New Password`;
        }
      };
    }

    // 7. Email Verification
    const verifyForm = document.getElementById("verify-form");
    if (verifyForm) {
      verifyForm.onsubmit = async (e) => {
        e.preventDefault();
        const token = document.getElementById("verify-token-input").value.trim();
        const submitBtn = document.getElementById("verify-submit-btn");

        submitBtn.disabled = true;
        submitBtn.innerHTML = `${renderIcon("loader", { size: "xs", className: "icon-spin" })} Validating...`;

        try {
          const res = await api.verifyEmail(token);
          showAlert(`${res.message} You can now sign in.`, "success");
          submitBtn.disabled = false;
          submitBtn.innerHTML = `${renderIcon("check-circle-2", { size: "sm" })} Verified`;
          setTimeout(() => {
            mode = "login";
            window.location.hash = "";
            render();
          }, 2000);
        } catch (err) {
          showAlert(err.message, "error");
          submitBtn.disabled = false;
          submitBtn.innerHTML = `${renderIcon("check-circle-2", { size: "sm" })} Verify Account Email`;
        }
      };
    }
  }

  // Initial mount render
  render();
}
