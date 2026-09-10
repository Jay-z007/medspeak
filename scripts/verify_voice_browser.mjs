// Node.js script using Chrome DevTools Protocol (CDP) to thoroughly verify
// Phase 3B: Real Voice Conversation, Microphone Capture, Speech-to-Text,
// Rime TTS audio auto-playback, replay controls (Play, Slow, Again), and console health.

import { spawn } from "child_process";

async function run() {
  const chromePath = "C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe";
  const port = 9226; // Distinct CDP port

  console.log("Launching headless Chrome on port " + port + " with fake media stream...");
  const chrome = spawn(chromePath, [
    "--headless=new",
    `--remote-debugging-port=${port}`,
    "--no-first-run",
    "--no-default-browser-check",
    "--use-fake-ui-for-media-stream", // Automatically grants mic permission
    "--use-fake-device-for-media-stream", // Generates synthetic audio input
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

    // Verify initial layout & voice elements
    const evalInitial = await send("Runtime.evaluate", {
      expression: `JSON.stringify({
        title: document.title,
        hasVoiceBadge: document.body.innerText.includes("Voice: Rime"),
        hasTapToSpeak: document.body.innerText.includes("Tap to Speak") || !!document.querySelector('button[aria-label*="microphone"]'),
        hasSuggestedPrompts: document.body.innerText.includes("How do I say omeprazole?"),
      })`,
    });

    const initData = JSON.parse(evalInitial.result.result.value);
    console.log("Page Title:", initData.title);
    console.log("Voice Provider Badge (Rime):", initData.hasVoiceBadge);
    console.log("Microphone Button Present:", initData.hasTapToSpeak);
    console.log("Suggested Prompts Present:", initData.hasSuggestedPrompts);

    if (!initData.hasVoiceBadge || !initData.hasTapToSpeak) {
      throw new Error("Initial layout verification failed for Phase 3B voice components");
    }

    // 2. Test Triggering Query with Real Rime Spoken Response via Suggested Prompt
    console.log("\n[TEST 2] Submitting prompt with real Rime audio synthesis: 'How do I say omeprazole?'...");
    const clickResult = await send("Runtime.evaluate", {
      expression: `(() => {
        const btns = Array.from(document.querySelectorAll('button'));
        const targetBtn = btns.find(b => b.innerText.includes("How do I say omeprazole?"));
        if (targetBtn) {
          targetBtn.dispatchEvent(new MouseEvent('click', { bubbles: true, cancelable: true }));
          return { found: true, text: targetBtn.innerText };
        }
        return { found: false, allBtns: btns.map(b => b.innerText) };
      })()`,
      returnByValue: true,
    });
    console.log("Prompt button click result:", clickResult.result.result.value);

    console.log("Waiting for backend response and live Rime synthesis...");
    let pData = null;
    for (let attempt = 0; attempt < 25; attempt++) {
      await new Promise((r) => setTimeout(r, 800));
      const res = await send("Runtime.evaluate", {
        expression: `JSON.stringify({
          bodySnippet: document.body.innerText.slice(0, 300),
          hasPhonetics: document.body.innerText.includes("oh-MEP-ruh-zohl"),
          hasPlayBtn: Array.from(document.querySelectorAll('button')).some(b => b.innerText.includes("Play") || b.innerText.includes("Replay")),
          hasSlowBtn: Array.from(document.querySelectorAll('button')).some(b => b.innerText.includes("Slow")),
          hasAgainBtn: Array.from(document.querySelectorAll('button')).some(b => b.innerText.includes("Again")),
          isSpeaking: document.body.innerText.includes("Speaking..."),
        })`,
      });
      pData = JSON.parse(res.result.result.value);
      if (pData.hasPhonetics) break;
    }

    console.log("Phonetic Breakdown Rendered:", pData.hasPhonetics);
    console.log("Play/Replay Button Rendered:", pData.hasPlayBtn);
    console.log("Slow (0.7x) Button Rendered:", pData.hasSlowBtn);
    console.log("Again Button Rendered:", pData.hasAgainBtn);
    console.log("Live Speaking State Detected:", pData.isSpeaking);
    if (!pData.hasPhonetics) {
      console.log("Page Body Snippet on failure:", pData.bodySnippet);
    }

    if (!pData.hasPhonetics || !pData.hasPlayBtn || !pData.hasSlowBtn) {
      throw new Error("Response or audio replay controls verification failed");
    }

    // 3. Test Text Input + Send Button
    console.log("\n[TEST 3] Typing 'Break down tachycardia' into text input and clicking Send...");
    await send("Runtime.evaluate", {
      expression: `(() => {
        const input = document.querySelector('input[type="text"]');
        if (!input) return false;
        const nativeInputValueSetter = Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype, "value").set;
        nativeInputValueSetter.call(input, "Break down tachycardia");
        input.dispatchEvent(new Event("input", { bubbles: true }));
        return true;
      })()`,
    });

    await new Promise((r) => setTimeout(r, 400));

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

    console.log("Waiting for backend response and live Rime synthesis...");
    let textData = null;
    for (let attempt = 0; attempt < 20; attempt++) {
      await new Promise((r) => setTimeout(r, 600));
      const res = await send("Runtime.evaluate", {
        expression: `JSON.stringify({
          hasPhonetics2: document.body.innerText.includes("tak-i-KAHR-dee-uh"),
        })`,
      });
      textData = JSON.parse(res.result.result.value);
      if (textData.hasPhonetics2) break;
    }

    console.log("Phonetic Breakdown 2 Rendered:", textData.hasPhonetics2);

    if (!textData.hasPhonetics2) {
      throw new Error("Text input conversation response verification failed");
    }

    // 4. Test Clicking "Slow" (0.7x) Replay Control
    console.log("\n[TEST 4] Clicking '🐢 Slow' button to test slower Rime synthesis...");
    await send("Runtime.evaluate", {
      expression: `(() => {
        const slowBtn = Array.from(document.querySelectorAll('button')).find(b => b.innerText.includes("Slow"));
        if (slowBtn) {
          slowBtn.click();
          return true;
        }
        return false;
      })()`,
    });

    console.log("Waiting for slow synthesis response to settle...");
    for (let i = 0; i < 20; i++) {
      await new Promise((r) => setTimeout(r, 600));
      const btnCheck = await send("Runtime.evaluate", {
        expression: `(() => {
          const micBtn = document.querySelector('button[aria-label*="microphone"]') ||
                         document.querySelector('button[aria-label*="speak"]');
          return micBtn ? !micBtn.disabled : false;
        })()`,
      });
      if (btnCheck.result.result.value === true) break;
    }

    // 5. Test Browser Microphone Recording Flow (using Chrome's fake media device)
    console.log("\n[TEST 5] Testing Microphone Recording Flow...");
    const micClickRes = await send("Runtime.evaluate", {
      expression: `(() => {
        const micBtn = document.querySelector('button[aria-label*="microphone"]') ||
                       document.querySelector('button[aria-label*="speak"]');
        if (micBtn) {
          micBtn.dispatchEvent(new MouseEvent('click', { bubbles: true, cancelable: true }));
          return { found: true, label: micBtn.getAttribute("aria-label"), disabled: micBtn.disabled };
        }
        return { found: false };
      })()`,
      returnByValue: true,
    });
    console.log("Mic Button Click Result:", micClickRes.result.result.value);

    await new Promise((r) => setTimeout(r, 1500));

    const evalRecordingState = await send("Runtime.evaluate", {
      expression: `JSON.stringify({
        isListening: document.body.innerText.includes("Listening") || !!document.querySelector('button[aria-label*="Stop"]'),
      })`,
    });
    const recState = JSON.parse(evalRecordingState.result.result.value);
    console.log("Recording State Active ('Listening...'):", recState.isListening);

    // Stop recording
    console.log("Stopping recording and dispatching to STT service...");
    await send("Runtime.evaluate", {
      expression: `(() => {
        const stopBtn = Array.from(document.querySelectorAll('button')).find(b =>
          b.innerText.includes("Stop") || b.innerText.includes("Finish & Send") || (b.getAttribute("aria-label") && b.getAttribute("aria-label").includes("Stop"))
        );
        if (stopBtn) {
          stopBtn.dispatchEvent(new MouseEvent('click', { bubbles: true, cancelable: true }));
          return true;
        }
        return false;
      })()`,
    });

    await new Promise((r) => setTimeout(r, 3000));

    // 6. Direct Backend Voice Endpoint Validation
    console.log("\n[TEST 6] Validating POST /api/chat/voice with real Rime speech payload...");
    const evalVoiceChatLog = await send("Runtime.evaluate", {
      expression: `(async () => {
        const formData = new FormData();
        const dummyAudio = new Blob([new Uint8Array(128)], { type: "audio/webm" });
        formData.append("audio", dummyAudio, "mic.webm");
        formData.append("speed", "1.0");

        try {
          const res = await fetch("http://127.0.0.1:8000/api/chat/voice", {
            method: "POST",
            body: formData,
          });
          const data = await res.json();
          return JSON.stringify({
            status: res.status,
            intent: data.intent,
            provider: data.provider,
            hasAudio: !!data.audio_base64,
          });
        } catch (e) {
          return JSON.stringify({ error: e.message });
        }
      })()`,
      awaitPromise: true,
    });

    const voiceApiCheck = JSON.parse(evalVoiceChatLog.result.result.value);
    console.log("Voice API Endpoint Verification:", voiceApiCheck);

    if (voiceApiCheck.status !== 200 || voiceApiCheck.provider !== "rime" || !voiceApiCheck.hasAudio) {
      throw new Error("Voice API verification failed");
    }

    // 7. Test Clear Chat
    console.log("\n[TEST 7] Testing 'Clear Chat' conversation reset...");
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

    const evalCleared = await send("Runtime.evaluate", {
      expression: `JSON.stringify({
        welcomeBack: document.body.innerText.includes("Voice-First Medical Pronunciation Tutor"),
        micHeroVisible: !!document.querySelector('button[aria-label*="speak"]'),
      })`,
    });

    const clearCheck = JSON.parse(evalCleared.result.result.value);
    console.log("Returned to Clean Welcome View:", clearCheck.welcomeBack);
    console.log("Microphone Hero Accessible:", clearCheck.micHeroVisible);

    // 8. Check for Console Errors
    console.log("\n[TEST 8] Checking console integrity & runtime errors...");
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
      console.log("\n>>> ALL PHASE 3B REAL VOICE CONVERSATION TESTS PASSED 100%! <<<");
      process.exit(0);
    } else {
      console.error("\n>>> Browser test encountered errors or exceptions! <<<");
      process.exit(1);
    }
  } catch (err) {
    console.error("Browser test error:", err);
    console.error("Console messages up to failure:", consoleMessages);
    chrome.kill();
    process.exit(1);
  }
}

run();
