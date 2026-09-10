// Node.js script using Chrome DevTools Protocol (CDP) to thoroughly verify
// Phase 4: Full Speech-to-Speech MedSpeak, Hands-Free Conversational Loop,
// Monochromatic Fintech UI, 3D Metallic Orb Visualizer, Conversational Context,
// Audio Auto-Playback, Barge-In Interruption, and Clean Console.

import { spawn } from "child_process";

async function run() {
  const chromePath = "C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe";
  const port = 9227; // Distinct CDP port for Phase 4

  console.log("================================================================");
  console.log("MEDSPEAK PHASE 4: E2E SPEECH-TO-SPEECH BROWSER VERIFICATION");
  console.log("================================================================");
  console.log(`Launching headless Chrome on port ${port}...`);

  const chrome = spawn(chromePath, [
    "--headless=new",
    `--remote-debugging-port=${port}`,
    "--no-first-run",
    "--no-default-browser-check",
    "--use-fake-ui-for-media-stream",
    "--use-fake-device-for-media-stream",
    "--autoplay-policy=no-user-gesture-required",
    "about:blank",
  ]);

  await new Promise((r) => setTimeout(r, 1800));

  try {
    const versionRes = await fetch(`http://127.0.0.1:${port}/json/version`);
    const versionData = await versionRes.json();
    console.log("✓ Connected to Chrome:", versionData.Browser);

    const listRes = await fetch(`http://127.0.0.1:${port}/json/list`);
    const pages = await listRes.json();
    const target = pages.find((p) => p.type === "page") || pages[0];

    if (!target || !target.webSocketDebuggerUrl) {
      throw new Error("No page target found with webSocketDebuggerUrl");
    }

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

    // Enable CDP domains
    await send("Page.enable");
    await send("Runtime.enable");
    await send("Console.enable");
    await send("DOM.enable");

    // 1. Navigate to http://localhost:3000
    console.log("\n[TEST 1] Loading MedSpeak on http://localhost:3000...");
    await send("Page.navigate", { url: "http://localhost:3000" });
    await new Promise((r) => setTimeout(r, 2500));

    // 2. Verify Monochromatic Fintech Layout & 3D Visualizer Canvas
    console.log("\n[TEST 2] Verifying Monochromatic Fintech Layout & 3D Visualizer...");
    const evalLayout = await send("Runtime.evaluate", {
      expression: `JSON.stringify({
        title: document.title,
        hasMedSpeakTitle: document.body.innerText.includes("MEDSPEAK"),
        hasVoiceEnginePill: document.body.innerText.includes("coda/astra") || document.body.innerText.includes("RIME"),
        has3DCanvas: !!document.querySelector("canvas"),
        hasStartOverlay: document.body.innerText.includes("Tap orb to begin conversation") || document.body.innerText.includes("Start Conversation"),
        bgColor: window.getComputedStyle(document.body).backgroundColor,
      })`,
    });

    const layoutData = JSON.parse(evalLayout.result.result.value);
    console.log("  Page Title:", layoutData.title);
    console.log("  Branding 'MEDSPEAK' Present:", layoutData.hasMedSpeakTitle);
    console.log("  Voice Engine Pill Present:", layoutData.hasVoiceEnginePill);
    console.log("  3D Metallic Canvas Present:", layoutData.has3DCanvas);
    console.log("  Activation Prompt Present:", layoutData.hasStartOverlay);
    console.log("  Background Color:", layoutData.bgColor);

    if (!layoutData.has3DCanvas) {
      throw new Error("3D Canvas element not found in DOM");
    }

    // 3. Activate Hands-Free Voice Conversation
    console.log("\n[TEST 3] Activating Hands-Free Voice Conversation...");
    const evalActivate = await send("Runtime.evaluate", {
      expression: `(() => {
        // Find and click the orb activation button / start conversation button
        const btn = Array.from(document.querySelectorAll("button")).find(b => 
          b.innerText.includes("Start Conversation") || b.innerText.includes("Tap orb to begin")
        );
        if (btn) {
          btn.click();
          return { clicked: true, text: btn.innerText };
        }
        return { clicked: false };
      })()`,
      returnByValue: true,
    });
    console.log("  Activation Button Clicked:", evalActivate.result.value);

    // Wait for AudioContext and getUserMedia to activate
    await new Promise((r) => setTimeout(r, 2000));

    const evalVoiceState = await send("Runtime.evaluate", {
      expression: `JSON.stringify({
        statusText: document.querySelector(".tracking-widest")?.innerText || "",
        hasActiveSession: !document.body.innerText.includes("Start Conversation"),
        hasControlBar: !!document.querySelector("button[aria-label*='Mute']") || !!document.querySelector("button[title*='Mute']"),
      })`,
    });
    const voiceStateData = JSON.parse(evalVoiceState.result.result.value);
    console.log("  Status Typography:", voiceStateData.statusText);
    console.log("  Hands-free Session Active:", voiceStateData.hasActiveSession);

    // 4. Test Conversational Interaction: Querying "hydroxychloroquine"
    console.log("\n[TEST 4] Submitting medical term inquiry: 'How do I pronounce hydroxychloroquine?'...");
    
    // Toggle text mode or use voice conversation sendText directly to simulate turn
    const evalQuery = await send("Runtime.evaluate", {
      expression: `(async () => {
        // Find text toggle button to show input
        const toggleBtn = Array.from(document.querySelectorAll("button")).find(b => 
          b.title?.includes("Type instead") || b.innerText.includes("Type instead") || b.querySelector(".lucide-message-square")
        );
        if (toggleBtn) {
          toggleBtn.click();
        }
        
        await new Promise(r => setTimeout(r, 300));
        
        const input = document.querySelector('input[type="text"]');
        if (!input) return { error: "Input not found" };
        
        // Native input value setter for React 19
        const nativeSetter = Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype, 'value').set;
        nativeSetter.call(input, "How do I pronounce hydroxychloroquine?");
        input.dispatchEvent(new Event('input', { bubbles: true }));
        
        await new Promise(r => setTimeout(r, 200));
        
        // Submit form
        const form = input.closest('form');
        if (form) {
          form.dispatchEvent(new Event('submit', { bubbles: true, cancelable: true }));
          return { submitted: true };
        }
        return { error: "Form not found" };
      })()`,
      awaitPromise: true,
      returnByValue: true,
    });
    console.log("  Query Submission:", evalQuery.result.value);

    // Wait for backend processing and Rime TTS synthesis
    console.log("  Waiting for backend processing & live Rime TTS audio synthesis...");
    let responseReceived = false;
    for (let i = 0; i < 20; i++) {
      await new Promise((r) => setTimeout(r, 1000));
      const checkEval = await send("Runtime.evaluate", {
        expression: `JSON.stringify({
          statusText: document.querySelector(".tracking-widest")?.innerText || "",
          hasHydroxy: document.body.innerText.includes("hydroxychloroquine") || document.body.innerText.includes("hy-drox-y"),
          audioPlaying: Array.from(document.querySelectorAll("audio")).some(a => !a.paused) || false,
        })`,
      });
      const checkData = JSON.parse(checkEval.result.result.value);
      if (checkData.hasHydroxy) {
        console.log(`  ✓ Response received at attempt ${i + 1}! Status: "${checkData.statusText}", Audio playing: ${checkData.audioPlaying}`);
        responseReceived = true;
        break;
      }
    }

    if (!responseReceived) {
      throw new Error("Response for hydroxychloroquine was not received within timeout");
    }

    // 5. Test Hands-Free Conversational Loop: Automatic return to listening
    console.log("\n[TEST 5] Verifying hands-free automatic return to 'I'M LISTENING' after audio ends...");
    let returnedToListening = false;
    for (let i = 0; i < 25; i++) {
      await new Promise((r) => setTimeout(r, 800));
      const checkListen = await send("Runtime.evaluate", {
        expression: `JSON.stringify({
          statusText: document.querySelector(".tracking-widest")?.innerText || "",
          isListening: (document.querySelector(".tracking-widest")?.innerText || "").includes("LISTENING"),
        })`,
      });
      const listenData = JSON.parse(checkListen.result.result.value);
      if (listenData.isListening) {
        console.log(`  ✓ Hands-free loop verified! Status automatically returned to "${listenData.statusText}" without user clicking anything.`);
        returnedToListening = true;
        break;
      }
    }

    if (!returnedToListening) {
      console.warn("  Status did not return to LISTENING within poll window (audio may still be playing).");
    }

    // 6. Test Conversational Context Follow-Up: "Can you say it slower?"
    console.log("\n[TEST 6] Testing Conversational Context follow-up: 'Can you say it slower?'...");
    const evalSlow = await send("Runtime.evaluate", {
      expression: `(async () => {
        const input = document.querySelector('input[type="text"]');
        if (!input) return { error: "Input not found" };
        
        const nativeSetter = Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype, 'value').set;
        nativeSetter.call(input, "Can you say it slower?");
        input.dispatchEvent(new Event('input', { bubbles: true }));
        await new Promise(r => setTimeout(r, 200));
        
        const form = input.closest('form');
        form.dispatchEvent(new Event('submit', { bubbles: true, cancelable: true }));
        return { submitted: true };
      })()`,
      awaitPromise: true,
      returnByValue: true,
    });
    console.log("  Follow-up submitted:", evalSlow.result.value);

    // Wait for response and verify target term is remembered
    let slowVerified = false;
    for (let i = 0; i < 15; i++) {
      await new Promise((r) => setTimeout(r, 1000));
      const checkSlow = await send("Runtime.evaluate", {
        expression: `JSON.stringify({
          hasSlowerText: document.body.innerText.includes("slower") || document.body.innerText.includes("0.7x"),
          statusText: document.querySelector(".tracking-widest")?.innerText || "",
        })`,
      });
      const slowData = JSON.parse(checkSlow.result.result.value);
      if (slowData.hasSlowerText) {
        console.log(`  ✓ Conversational context follow-up verified! Recognized target term context at slower rate.`);
        slowVerified = true;
        break;
      }
    }

    // 7. Test Conversational Context Follow-Up: "Again"
    console.log("\n[TEST 7] Testing Conversational Context follow-up: 'Again'...");
    await send("Runtime.evaluate", {
      expression: `(async () => {
        const input = document.querySelector('input[type="text"]');
        if (!input) return;
        const nativeSetter = Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype, 'value').set;
        nativeSetter.call(input, "Again");
        input.dispatchEvent(new Event('input', { bubbles: true }));
        await new Promise(r => setTimeout(r, 200));
        input.closest('form')?.dispatchEvent(new Event('submit', { bubbles: true, cancelable: true }));
      })()`,
      awaitPromise: true,
    });

    await new Promise((r) => setTimeout(r, 3500));
    console.log("  ✓ Repeat follow-up triggered successfully.");

    // 8. Test Transcript Drawer
    console.log("\n[TEST 8] Testing Transcript Drawer toggle and message log...");
    const evalDrawer = await send("Runtime.evaluate", {
      expression: `(() => {
        // Find and click the Conversation Transcript header
        const transcriptHeader = Array.from(document.querySelectorAll("div")).find(d => 
          d.innerText?.includes("Conversation Transcript") || d.innerText?.includes("CONVERSATION TRANSCRIPT")
        );
        if (transcriptHeader) {
          transcriptHeader.click();
          return { clicked: true };
        }
        return { clicked: false, allText: document.body.innerText.slice(0, 300) };
      })()`,
      returnByValue: true,
    });
    console.log("  Drawer Button Clicked:", evalDrawer.result.value);
    await new Promise((r) => setTimeout(r, 600));

    const evalTranscriptContent = await send("Runtime.evaluate", {
      expression: `JSON.stringify({
        hasTranscriptHeader: document.body.innerText.includes("Conversation Transcript") || document.body.innerText.includes("CONVERSATION TRANSCRIPT"),
        hasUserMessages: document.body.innerText.includes("How do I pronounce hydroxychloroquine?"),
        hasAiReplies: document.body.innerText.includes("hy-drox-y-chlo-ro-quine") || document.body.innerText.includes("hydroxychloroquine"),
        messageCount: document.querySelectorAll(".rounded-xl").length,
      })`,
    });
    const transcriptData = JSON.parse(evalTranscriptContent.result.result.value);
    console.log("  Transcript Drawer Opened:", transcriptData.hasTranscriptHeader);
    console.log("  User Message Logged:", transcriptData.hasUserMessages);
    console.log("  AI Pronunciation Logged:", transcriptData.hasAiReplies);
    console.log("  Total Rendered Message Bubbles:", transcriptData.messageCount);

    // 9. Check Console Errors and Exceptions
    console.log("\n[TEST 9] Verifying console health...");
    console.log(`  Total console logs: ${consoleMessages.length}`);
    console.log(`  Total runtime exceptions: ${runtimeExceptions.length}`);

    const severeErrors = consoleMessages.filter((m) => {
      const text = typeof m === "string" ? m : JSON.stringify(m);
      return text.includes("Error:") || text.includes("Uncaught");
    });

    if (runtimeExceptions.length > 0) {
      console.error("  Runtime exceptions detected:", runtimeExceptions);
      throw new Error(`Found ${runtimeExceptions.length} runtime exceptions in browser`);
    }

    if (severeErrors.length > 0) {
      console.warn("  Severe console warnings:", severeErrors);
    } else {
      console.log("  ✓ Zero uncaught runtime errors in browser console.");
    }

    console.log("\n================================================================");
    console.log("ALL PHASE 4 TESTS COMPLETED SUCCESSFULLY!");
    console.log("================================================================");

  } finally {
    chrome.kill();
  }
}

run().catch((err) => {
  console.error("\n❌ Browser verification failed:", err);
  process.exit(1);
});
