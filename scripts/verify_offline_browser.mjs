// Test offline state when backend is stopped
import { spawn } from "child_process";

async function run() {
  const chromePath = "C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe";
  const port = 9223;

  const chrome = spawn(chromePath, [
    "--headless=new",
    `--remote-debugging-port=${port}`,
    "--no-first-run",
    "--no-default-browser-check",
    "about:blank",
  ]);

  await new Promise((r) => setTimeout(r, 1500));

  try {
    const listRes = await fetch(`http://127.0.0.1:${port}/json/list`);
    const pages = await listRes.json();
    const target = pages.find((p) => p.type === "page") || pages[0];
    const ws = new WebSocket(target.webSocketDebuggerUrl);

    await new Promise((res, rej) => {
      ws.onopen = res;
      ws.onerror = rej;
    });

    let id = 1;
    const pending = new Map();
    ws.onmessage = (e) => {
      const msg = JSON.parse(e.data);
      if (msg.id && pending.has(msg.id)) {
        pending.get(msg.id)(msg);
        pending.delete(msg.id);
      }
    };

    function send(method, params = {}) {
      const cur = id++;
      return new Promise((r) => {
        pending.set(cur, r);
        ws.send(JSON.stringify({ id: cur, method, params }));
      });
    }

    await send("Page.enable");
    await send("Runtime.enable");

    await send("Page.navigate", { url: "http://localhost:3000" });
    await new Promise((r) => setTimeout(r, 2000));

    // Evaluate offline UI text when backend is stopped
    const evalRes = await send("Runtime.evaluate", {
      expression: `JSON.stringify({
        hasOfflineBadge: document.body.innerText.includes("Offline") || document.body.innerText.includes("Backend Connection Failed"),
        bodyText: document.body.innerText
      })`,
    });

    const parsed = JSON.parse(evalRes.result.result.value);
    console.log("Offline UI Detected:", parsed.hasOfflineBadge);

    ws.close();
    chrome.kill();
    process.exit(parsed.hasOfflineBadge ? 0 : 1);
  } catch (e) {
    chrome.kill();
    console.error(e);
    process.exit(1);
  }
}

run();
