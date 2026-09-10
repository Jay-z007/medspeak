// Node.js script to test Chrome headless loading http://localhost:3000,
// verifying console logs, network responses, and button clicks via CDP.

import { spawn } from "child_process";

async function run() {
  const chromePath = "C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe";
  const port = 9222;

  console.log("Launching headless Chrome...");
  const chrome = spawn(chromePath, [
    "--headless=new",
    `--remote-debugging-port=${port}`,
    "--no-first-run",
    "--no-default-browser-check",
    "about:blank",
  ]);

  // Give Chrome a moment to start
  await new Promise((r) => setTimeout(r, 1500));

  try {
    // 1. Get browser targets
    const versionRes = await fetch(`http://127.0.0.1:${port}/json/version`);
    const versionData = await versionRes.json();
    console.log("Connected to Chrome:", versionData.Browser);

    const listRes = await fetch(`http://127.0.0.1:${port}/json/list`);
    const pages = await listRes.json();
    const target = pages.find((p) => p.type === "page") || pages[0];

    if (!target || !target.webSocketDebuggerUrl) {
      throw new Error("No page target found with webSocketDebuggerUrl");
    }

    console.log("Page target found:", target.id);
    const ws = new WebSocket(target.webSocketDebuggerUrl);

    await new Promise((resolve, reject) => {
      ws.onopen = resolve;
      ws.onerror = reject;
    });

    let msgId = 1;
    const pending = new Map();
    const consoleMessages = [];
    const runtimeExceptions = [];

    ws.onmessage = (event) => {
      const msg = JSON.parse(event.data);
      if (msg.id && pending.has(msg.id)) {
        pending.get(msg.id)(msg);
        pending.delete(msg.id);
      }
      if (msg.method === "Console.messageAdded") {
        consoleMessages.push(msg.params.message);
      }
      if (msg.method === "Runtime.consoleAPICalled") {
        consoleMessages.push(msg.params);
      }
      if (msg.method === "Runtime.exceptionThrown") {
        runtimeExceptions.push(msg.params);
      }
    };

    function send(method, params = {}) {
      const id = msgId++;
      return new Promise((resolve) => {
        pending.set(id, resolve);
        ws.send(JSON.stringify({ id, method, params }));
      });
    }

    // Enable domains
    await send("Page.enable");
    await send("Runtime.enable");
    await send("Console.enable");
    await send("DOM.enable");

    // Navigate to http://localhost:3000
    console.log("Navigating to http://localhost:3000...");
    await send("Page.navigate", { url: "http://localhost:3000" });

    // Wait 3 seconds for React hydration and initial fetch
    await new Promise((r) => setTimeout(r, 3000));

    // Evaluate document title and content
    const evalContent = await send("Runtime.evaluate", {
      expression: `JSON.stringify({
        title: document.title,
        heading: document.querySelector('h1')?.innerText,
        statusText: document.body.innerText,
        hasRefreshBtn: !!document.querySelector('button[aria-label="Refresh Backend Health Status"]'),
        hasPingBtn: !!document.querySelector('button[aria-label="Send Real-Time Ping to FastAPI Health Endpoint"]'),
      })`,
    });

    const parsed = JSON.parse(evalContent.result.result.value);
    console.log("Page Heading:", parsed.heading);
    console.log("Refresh Button Exists:", parsed.hasRefreshBtn);
    console.log("Test Connection Button Exists:", parsed.hasPingBtn);

    // Test clicking the "Test Connection" button
    console.log("Clicking 'Test Connection' button...");
    await send("Runtime.evaluate", {
      expression: `document.querySelector('button[aria-label="Send Real-Time Ping to FastAPI Health Endpoint"]').click()`,
    });

    // Wait 1.5 seconds for ping to resolve
    await new Promise((r) => setTimeout(r, 1500));

    const evalAfterPing = await send("Runtime.evaluate", {
      expression: `JSON.stringify({
        pingSuccess: document.body.innerText.includes("Success: Response in"),
        bodySnippet: document.body.innerText.slice(0, 500)
      })`,
    });

    const pingCheck = JSON.parse(evalAfterPing.result.result.value);
    console.log("Diagnostic Ping Succeeded:", pingCheck.pingSuccess);

    // Report console messages and runtime exceptions
    console.log("Console Messages Count:", consoleMessages.length);
    console.log("Runtime Exceptions Count:", runtimeExceptions.length);
    if (runtimeExceptions.length > 0) {
      console.error("Runtime Exceptions:", JSON.stringify(runtimeExceptions, null, 2));
    }

    ws.close();
    chrome.kill();

    if (runtimeExceptions.length === 0 && pingCheck.pingSuccess) {
      console.log("ALL BROWSER TESTS PASSED!");
      process.exit(0);
    } else {
      console.error("Browser test verification failed!");
      process.exit(1);
    }
  } catch (err) {
    console.error("Error during browser testing:", err);
    chrome.kill();
    process.exit(1);
  }
}

run();
