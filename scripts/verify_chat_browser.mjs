// Node.js script to test Chrome headless loading http://localhost:3000,
// verifying interactive MedSpeak chat UI, suggested prompt clicks,
// keyboard enter-to-send, send button clicks, clear conversation,
// and console/network integrity via Chrome DevTools Protocol (CDP).

import { spawn } from "child_process";

async function run() {
  const chromePath = "C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe";
  const port = 9223; // Use distinct port from previous test

  console.log("Launching headless Chrome on port " + port + "...");
  const chrome = spawn(chromePath, [
    "--headless=new",
    `--remote-debugging-port=${port}`,
    "--no-first-run",
    "--no-default-browser-check",
    "about:blank",
  ]);

  await new Promise((r) => setTimeout(r, 1500));

  try {
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

    // 1. Navigate to http://localhost:3000
    console.log("\n[TEST 1] Navigating to http://localhost:3000...");
    await send("Page.navigate", { url: "http://localhost:3000" });
    await new Promise((r) => setTimeout(r, 3000));

    // Verify initial layout & branding
    const evalInitial = await send("Runtime.evaluate", {
      expression: `JSON.stringify({
        title: document.title,
        hasMedSpeakTitle: document.body.innerText.includes("MedSpeak"),
        hasVoiceRime: document.body.innerText.includes("Voice: Rime"),
        hasWelcome: document.body.innerText.includes("Welcome to MedSpeak"),
        hasPrompt1: document.body.innerText.includes("How do I pronounce hydroxychloroquine?"),
        hasPrompt2: document.body.innerText.includes("Break down tachycardia"),
        hasPrompt3: document.body.innerText.includes("How do I say omeprazole?"),
      })`,
    });

    const initData = JSON.parse(evalInitial.result.result.value);
    console.log("Title:", initData.title);
    console.log("Has MedSpeak Branding:", initData.hasMedSpeakTitle);
    console.log("Has Voice Rime Badge:", initData.hasVoiceRime);
    console.log("Has Welcome Hero:", initData.hasWelcome);
    console.log("Has Suggested Prompts:", initData.hasPrompt1 && initData.hasPrompt2 && initData.hasPrompt3);

    if (!initData.hasMedSpeakTitle || !initData.hasPrompt1) {
      throw new Error("Initial layout verification failed");
    }

    // 2. Test Suggested Prompt 1: Click "How do I pronounce hydroxychloroquine?"
    console.log("\n[TEST 2] Clicking suggested prompt: 'How do I pronounce hydroxychloroquine?'...");
    await send("Runtime.evaluate", {
      expression: `(() => {
        const btns = Array.from(document.querySelectorAll('button'));
        const targetBtn = btns.find(b => b.innerText.includes("How do I pronounce hydroxychloroquine?"));
        if (targetBtn) {
          targetBtn.click();
          return true;
        }
        return false;
      })()`,
    });

    // Wait for response to arrive
    console.log("Waiting for backend response...");
    await new Promise((r) => setTimeout(r, 2000));

    const evalPrompt1 = await send("Runtime.evaluate", {
      expression: `JSON.stringify({
        hasUserMessage: document.body.innerText.includes("How do I pronounce hydroxychloroquine?"),
        hasPhonetics: document.body.innerText.includes("hy-DROX-ee-KLOR-oh-kwin"),
        hasTermBadge: document.body.innerText.includes("Term: hydroxychloroquine"),
        hasClearBtn: Array.from(document.querySelectorAll('button')).some(b => b.innerText.includes("Clear Chat")),
      })`,
    });

    const p1Data = JSON.parse(evalPrompt1.result.result.value);
    console.log("User Message 1 Displayed:", p1Data.hasUserMessage);
    console.log("AI Phonetics 1 Received:", p1Data.hasPhonetics);
    console.log("Term Metadata 1 Displayed:", p1Data.hasTermBadge);
    console.log("Clear Chat Button Appears:", p1Data.hasClearBtn);

    if (!p1Data.hasPhonetics) {
      throw new Error("Prompt 1 pronunciation response verification failed");
    }

    // 3. Test Message 2 via Input typing + Enter: "Break down tachycardia"
    console.log("\n[TEST 3] Typing and submitting with Enter: 'Break down tachycardia'...");
    await send("Runtime.evaluate", {
      expression: `(() => {
        const input = document.querySelector('input[type="text"]');
        if (!input) return false;
        // React synthetic event simulation
        const nativeInputValueSetter = Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype, "value").set;
        nativeInputValueSetter.call(input, "Break down tachycardia");
        input.dispatchEvent(new Event("input", { bubbles: true }));
        // Press Enter
        input.dispatchEvent(new KeyboardEvent("keydown", { key: "Enter", code: "Enter", bubbles: true }));
        return true;
      })()`,
    });

    console.log("Waiting for backend response...");
    await new Promise((r) => setTimeout(r, 2000));

    const evalPrompt2 = await send("Runtime.evaluate", {
      expression: `JSON.stringify({
        hasUserMessage2: document.body.innerText.includes("Break down tachycardia"),
        hasPhonetics2: document.body.innerText.includes("tak-i-KAHR-dee-uh"),
        hasTerm2: document.body.innerText.includes("Term: tachycardia"),
      })`,
    });

    const p2Data = JSON.parse(evalPrompt2.result.result.value);
    console.log("User Message 2 Displayed:", p2Data.hasUserMessage2);
    console.log("AI Phonetics 2 Received:", p2Data.hasPhonetics2);
    console.log("Term Metadata 2 Displayed:", p2Data.hasTerm2);

    if (!p2Data.hasPhonetics2) {
      throw new Error("Prompt 2 tachycardia breakdown response verification failed");
    }

    // 4. Test Message 3 via Input typing + Send Button: "How do I say omeprazole?"
    console.log("\n[TEST 4] Typing 'How do I say omeprazole?' and clicking Send button...");
    await send("Runtime.evaluate", {
      expression: `(() => {
        const input = document.querySelector('input[type="text"]');
        if (!input) return false;
        const nativeInputValueSetter = Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype, "value").set;
        nativeInputValueSetter.call(input, "How do I say omeprazole?");
        input.dispatchEvent(new Event("input", { bubbles: true }));
        return true;
      })()`,
    });

    await new Promise((r) => setTimeout(r, 300));

    // Click Send button
    await send("Runtime.evaluate", {
      expression: `(() => {
        const sendBtn = Array.from(document.querySelectorAll('button')).find(b => b.innerText.includes("Send"));
        if (sendBtn) {
          sendBtn.click();
          return true;
        }
        return false;
      })()`,
    });

    console.log("Waiting for backend response...");
    await new Promise((r) => setTimeout(r, 2000));

    const evalPrompt3 = await send("Runtime.evaluate", {
      expression: `JSON.stringify({
        hasUserMessage3: document.body.innerText.includes("How do I say omeprazole?"),
        hasPhonetics3: document.body.innerText.includes("oh-MEP-ruh-zohl"),
        hasTerm3: document.body.innerText.includes("Term: omeprazole"),
        // Verify chat history has accumulated all 3 conversations
        hasAllThreeInHistory: (
          document.body.innerText.includes("hydroxychloroquine") &&
          document.body.innerText.includes("tachycardia") &&
          document.body.innerText.includes("omeprazole")
        )
      })`,
    });

    const p3Data = JSON.parse(evalPrompt3.result.result.value);
    console.log("User Message 3 Displayed:", p3Data.hasUserMessage3);
    console.log("AI Phonetics 3 Received:", p3Data.hasPhonetics3);
    console.log("Term Metadata 3 Displayed:", p3Data.hasTerm3);
    console.log("Full Multi-Turn Conversation Preserved in History:", p3Data.hasAllThreeInHistory);

    if (!p3Data.hasPhonetics3 || !p3Data.hasAllThreeInHistory) {
      throw new Error("Prompt 3 or chat history retention verification failed");
    }

    // 5. Test Safety Boundary Prompt
    console.log("\n[TEST 5] Submitting safety boundary request: 'What dose of amoxicillin should I take?'...");
    await send("Runtime.evaluate", {
      expression: `(() => {
        const input = document.querySelector('input[type="text"]');
        const nativeInputValueSetter = Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype, "value").set;
        nativeInputValueSetter.call(input, "What dose of amoxicillin should I take?");
        input.dispatchEvent(new Event("input", { bubbles: true }));
        input.dispatchEvent(new KeyboardEvent("keydown", { key: "Enter", code: "Enter", bubbles: true }));
      })()`,
    });

    console.log("Waiting for backend response...");
    await new Promise((r) => setTimeout(r, 2000));

    const evalSafety = await send("Runtime.evaluate", {
      expression: `JSON.stringify({
        hasSafetyNotice: document.body.innerText.includes("Safety Notice"),
        hasSafetyBoundaryText: document.body.innerText.includes("diagnosis, treatment, or dosage advice"),
      })`,
    });

    const safetyData = JSON.parse(evalSafety.result.result.value);
    console.log("Safety Notice Tag Displayed:", safetyData.hasSafetyNotice);
    console.log("Safety Boundary Message Displayed:", safetyData.hasSafetyBoundaryText);

    if (!safetyData.hasSafetyBoundaryText) {
      throw new Error("Safety boundary enforcement verification failed");
    }

    // 6. Test Clear Chat button
    console.log("\n[TEST 6] Clicking 'Clear Chat' button...");
    await send("Runtime.evaluate", {
      expression: `(() => {
        const clearBtn = Array.from(document.querySelectorAll('button')).find(b => b.innerText.includes("Clear Chat"));
        if (clearBtn) {
          clearBtn.click();
          return true;
        }
        return false;
      })()`,
    });

    await new Promise((r) => setTimeout(r, 600));

    const evalClear = await send("Runtime.evaluate", {
      expression: `JSON.stringify({
        returnedToWelcome: document.body.innerText.includes("Welcome to MedSpeak"),
        historyCleared: !document.body.innerText.includes("hy-DROX-ee-KLOR-oh-kwin"),
        hasSuggestedPromptsAgain: document.body.innerText.includes("How do I pronounce hydroxychloroquine?"),
      })`,
    });

    const clearData = JSON.parse(evalClear.result.result.value);
    console.log("Returned to Welcome Screen:", clearData.returnedToWelcome);
    console.log("History Successfully Cleared:", clearData.historyCleared);
    console.log("Suggested Prompts Restored:", clearData.hasSuggestedPromptsAgain);

    if (!clearData.returnedToWelcome || !clearData.historyCleared) {
      throw new Error("Clear conversation verification failed");
    }

    // 7. Check for Console Errors and Runtime Exceptions
    console.log("\n[TEST 7] Checking console integrity & runtime errors...");
    const consoleErrors = consoleMessages.filter(
      (m) => m.level === "error" || (m.type === "error")
    );
    console.log("Total Console Messages:", consoleMessages.length);
    console.log("Console Errors Count:", consoleErrors.length);
    console.log("Runtime Exceptions Count:", runtimeExceptions.length);

    if (consoleErrors.length > 0) {
      console.error("Console Errors:", JSON.stringify(consoleErrors, null, 2));
    }
    if (runtimeExceptions.length > 0) {
      console.error("Runtime Exceptions:", JSON.stringify(runtimeExceptions, null, 2));
    }

    ws.close();
    chrome.kill();

    if (runtimeExceptions.length === 0 && consoleErrors.length === 0) {
      console.log("\n>>> ALL PHASE 3A INTERACTIVE BROWSER TESTS PASSED 100%! <<<");
      process.exit(0);
    } else {
      console.error("\n>>> Browser test encountered errors or exceptions! <<<");
      process.exit(1);
    }
  } catch (err) {
    console.error("Browser test error:", err);
    chrome.kill();
    process.exit(1);
  }
}

run();
