const http = require("http");
const fs = require("fs");
const path = require("path");
const { spawn } = require("child_process");

const CHROME_PATH = "C:\\Program Files (x86)\\Google\\Chrome\\Application\\chrome.exe";
const USER_DATA = path.join("C:\\CLoudProject\\data", "chrome_profile_" + Date.now());
const SCREENSHOT_DIR = "C:\\CLoudProject\\docs\\screenshots";

function sleep(ms) {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

function httpGet(url) {
  return new Promise((resolve, reject) => {
    http.get(url, (res) => {
      let data = "";
      res.on("data", (chunk) => (data += chunk));
      res.on("end", () => {
        try {
          resolve(JSON.parse(data));
        } catch (e) {
          resolve(data);
        }
      });
    }).on("error", reject);
  });
}

class CDPClient {
  constructor(wsUrl) {
    this.ws = new WebSocket(wsUrl);
    this.id = 1;
    this.pending = new Map();

    this.ws.onmessage = (event) => {
      const msg = JSON.parse(event.data);
      if (msg.id && this.pending.has(msg.id)) {
        const { resolve, reject } = this.pending.get(msg.id);
        this.pending.delete(msg.id);
        if (msg.error) reject(new Error(msg.error.message));
        else resolve(msg.result);
      }
    };
  }

  async ready() {
    if (this.ws.readyState === WebSocket.OPEN) return;
    return new Promise((resolve, reject) => {
      this.ws.onopen = resolve;
      this.ws.onerror = reject;
    });
  }

  send(method, params = {}) {
    const id = this.id++;
    return new Promise((resolve, reject) => {
      this.pending.set(id, { resolve, reject });
      this.ws.send(JSON.stringify({ id, method, params }));
    });
  }

  async eval(expression) {
    const res = await this.send("Runtime.evaluate", {
      expression,
      awaitPromise: true,
      returnByValue: true,
    });
    return res.result?.value;
  }

  async screenshot(filePath) {
    const res = await this.send("Page.captureScreenshot", { format: "png" });
    const buffer = Buffer.from(res.data, "base64");
    fs.writeFileSync(filePath, buffer);
    console.log(`Saved screenshot: ${filePath}`);
  }

  close() {
    this.ws.close();
  }
}

async function main() {
  const prefix = process.argv[2] || "before";
  console.log(`Starting screenshot capture with prefix: ${prefix}`);

  if (!fs.existsSync(SCREENSHOT_DIR)) {
    fs.mkdirSync(SCREENSHOT_DIR, { recursive: true });
  }

  const chromeProc = spawn(
    CHROME_PATH,
    [
      "--headless=new",
      "--no-sandbox",
      "--disable-dev-shm-usage",
      "--disable-gpu",
      "--no-first-run",
      "--no-default-browser-check",
      `--user-data-dir=${USER_DATA}`,
      "--remote-debugging-port=9222",
      "--window-size=1440,900",
      "about:blank",
    ],
    { stdio: "inherit" }
  );

  let connected = false;
  let target = null;
  for (let i = 0; i < 30; i++) {
    await sleep(500);
    try {
      const list = await httpGet("http://127.0.0.1:9222/json");
      if (Array.isArray(list) && list.length > 0) {
        target = list[0];
        connected = true;
        break;
      }
    } catch (e) {
      if (i % 5 === 0) console.log(`Polling CDP (attempt ${i}): ${e.message}`);
    }
  }

  if (!connected) {
    console.error("Could not connect to Chrome DevTools port 9222");
    chromeProc.kill();
    process.exit(1);
  }

  console.log("Connected to Chrome CDP:", target.webSocketDebuggerUrl);
  const cdp = new CDPClient(target.webSocketDebuggerUrl);
  await cdp.ready();
  await cdp.send("Network.enable");
  await cdp.send("Network.setCacheDisabled", { cacheDisabled: true });
  await cdp.send("Page.enable");
  await cdp.send("Runtime.enable");

  // Navigate to dashboard with cache disabled
  console.log("Navigating to http://127.0.0.1:8000/dashboard/...");
  await cdp.send("Page.navigate", { url: "http://127.0.0.1:8000/dashboard/" });
  await sleep(2000);

  // Capture Login view
  await cdp.screenshot(path.join(SCREENSHOT_DIR, `${prefix}_login.png`));

  // Perform programmatic login inside the page context
  console.log("Submitting login credentials...");
  await cdp.eval(`
    (async () => {
      const emailInput = document.getElementById("login-email");
      const passInput = document.getElementById("login-password");
      if (emailInput) emailInput.value = "s23_shaikh_irafan@mgmcen.ac.in";
      if (passInput) passInput.value = "@Shaikh921";
      const submitBtn = document.getElementById("login-submit-btn");
      if (submitBtn) submitBtn.click();
    })()
  `);
  await sleep(2500);

  // Capture Overview view
  await cdp.screenshot(path.join(SCREENSHOT_DIR, `${prefix}_overview.png`));

  // Navigate to Security & Threat
  console.log("Navigating to Security & Threat view...");
  await cdp.eval(`window.navigateTo("security")`);
  await sleep(1500);
  await cdp.screenshot(path.join(SCREENSHOT_DIR, `${prefix}_security.png`));

  // Navigate to Infrastructure
  console.log("Navigating to Infrastructure view...");
  await cdp.eval(`window.navigateTo("resources")`);
  await sleep(1500);
  await cdp.screenshot(path.join(SCREENSHOT_DIR, `${prefix}_infrastructure.png`));

  // Navigate to Lab PCs
  console.log("Navigating to Lab PCs view...");
  await cdp.eval(`window.navigateTo("lab")`);
  await sleep(1500);
  await cdp.screenshot(path.join(SCREENSHOT_DIR, `${prefix}_lab.png`));

  // Navigate to Anomaly Center
  console.log("Navigating to Anomaly Center view...");
  await cdp.eval(`window.navigateTo("anomalies")`);
  await sleep(1500);
  await cdp.screenshot(path.join(SCREENSHOT_DIR, `${prefix}_anomalies.png`));

  // Navigate to Cost Optimization
  console.log("Navigating to Cost view...");
  await cdp.eval(`window.navigateTo("cost")`);
  await sleep(1500);
  await cdp.screenshot(path.join(SCREENSHOT_DIR, `${prefix}_cost.png`));

  // Navigate to AI Incident Narrator
  console.log("Navigating to Narrator view...");
  await cdp.eval(`window.navigateTo("narrator")`);
  await sleep(1500);
  await cdp.screenshot(path.join(SCREENSHOT_DIR, `${prefix}_narrator.png`));

  // Navigate to Reports
  console.log("Navigating to Reports view...");
  await cdp.eval(`window.navigateTo("reports")`);
  await sleep(1500);
  await cdp.screenshot(path.join(SCREENSHOT_DIR, `${prefix}_reports.png`));

  // Navigate to Admin Management
  console.log("Navigating to Admin Management view...");
  await cdp.eval(`window.navigateTo("admin-management")`);
  await sleep(1500);
  await cdp.screenshot(path.join(SCREENSHOT_DIR, `${prefix}_admin_management.png`));

  // Navigate to Device Management
  console.log("Navigating to Device Management view...");
  await cdp.eval(`window.navigateTo("device-management")`);
  await sleep(1500);
  await cdp.screenshot(path.join(SCREENSHOT_DIR, `${prefix}_device_management.png`));

  // Navigate to Incidents
  console.log("Navigating to Incidents view...");
  await cdp.eval(`window.navigateTo("incidents")`);
  await sleep(1500);
  await cdp.screenshot(path.join(SCREENSHOT_DIR, `${prefix}_incidents.png`));

  // Navigate to Telemetry Stream
  console.log("Navigating to Telemetry Stream view...");
  await cdp.eval(`window.navigateTo("metrics")`);
  await sleep(2000);
  await cdp.screenshot(path.join(SCREENSHOT_DIR, `${prefix}_telemetry.png`));

  // Navigate to Audit Trail
  console.log("Navigating to Audit Trail view...");
  await cdp.eval(`window.navigateTo("audit")`);
  await sleep(1500);
  await cdp.screenshot(path.join(SCREENSHOT_DIR, `${prefix}_audit.png`));

  // Navigate to Threshold Rules
  console.log("Navigating to Threshold Rules view...");
  await cdp.eval(`window.navigateTo("settings")`);
  await sleep(1500);
  await cdp.screenshot(path.join(SCREENSHOT_DIR, `${prefix}_settings.png`));

  // Trigger New Rule Modal
  console.log("Triggering New Alert Rule modal...");
  await cdp.eval(`document.getElementById("create-rule-btn")?.click()`);
  await sleep(1000);
  await cdp.screenshot(path.join(SCREENSHOT_DIR, `${prefix}_modal.png`));
  await cdp.eval(`document.getElementById("modal-close-btn")?.click()`);
  await sleep(500);

  // Trigger Notification Drawer
  console.log("Triggering Notification Drawer...");
  await cdp.eval(`document.getElementById("notif-drawer-toggle")?.click()`);
  await sleep(1000);
  await cdp.screenshot(path.join(SCREENSHOT_DIR, `${prefix}_drawer.png`));
  await cdp.eval(`document.getElementById("close-notif-btn")?.click()`);
  await sleep(500);

  // Trigger Command Palette
  console.log("Triggering Command Palette...");
  await cdp.eval(`document.getElementById("global-search-trigger")?.click()`);
  await sleep(1000);
  await cdp.screenshot(path.join(SCREENSHOT_DIR, `${prefix}_palette.png`));

  cdp.close();
  chromeProc.kill();
  console.log("Done capturing all screenshots!");
}

main().catch((err) => {
  console.error("Error capturing screenshots:", err);
  process.exit(1);
});
