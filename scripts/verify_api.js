const http = require("http");

async function check(endpoint) {
  return new Promise((resolve) => {
    http.get(`http://127.0.0.1:8000${endpoint}`, (res) => {
      let data = "";
      res.on("data", (chunk) => (data += chunk));
      res.on("end", () => {
        resolve({
          endpoint,
          status: res.statusCode,
          contentType: res.headers["content-type"],
          length: data.length,
        });
      });
    }).on("error", (err) => {
      resolve({ endpoint, error: err.message });
    });
  });
}

async function main() {
  console.log("Validating Live FastAPI Endpoints...");
  const endpoints = [
    "/health",
    "/",
    "/api/v1/currency/supported",
    "/api/v1/summary",
    "/api/v1/hosts/",
    "/api/v1/alerts/",
    "/api/v1/security/events",
    "/dashboard/",
    "/css/design-system.css",
    "/css/command-center.css",
  ];

  for (const ep of endpoints) {
    const res = await check(ep);
    console.log(`Endpoint: ${res.endpoint} -> Status: ${res.status || 'ERROR'} (${res.contentType || res.error})`);
  }
}

main();
