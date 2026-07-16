const gateEl = document.getElementById("gate");
const gateForm = document.getElementById("gate-form");
const gateInput = document.getElementById("gate-input");
const gateError = document.getElementById("gate-error");
const chatEl = document.getElementById("chat");

const messagesEl = document.getElementById("messages");
const form = document.getElementById("composer");
const input = document.getElementById("input");
const sendBtn = document.getElementById("send-btn");

// Plain {role, content} history — this is the entire client-side state.
// The server re-derives any tool-use bookkeeping fresh on every turn.
const history = [];

// The access code is a shared secret, not a per-user credential — sessionStorage
// (not localStorage) so it doesn't silently persist across browser restarts
// on a shared machine.
const ACCESS_CODE_KEY = "cca_access_code";
let accessCode = sessionStorage.getItem(ACCESS_CODE_KEY) || "";

function showGate(errorMessage) {
  chatEl.hidden = true;
  gateEl.hidden = false;
  if (errorMessage) {
    gateError.textContent = errorMessage;
    gateError.hidden = false;
  } else {
    gateError.hidden = true;
  }
  gateInput.focus();
}

function unlockChat() {
  gateEl.hidden = true;
  chatEl.hidden = false;
  input.focus();
}

gateForm.addEventListener("submit", (e) => {
  e.preventDefault();
  const code = gateInput.value.trim();
  if (!code) return;
  accessCode = code;
  sessionStorage.setItem(ACCESS_CODE_KEY, code);
  gateInput.value = "";
  unlockChat();
});

if (accessCode) {
  // Optimistic — validated for real on the first /api/chat call below.
  unlockChat();
} else {
  showGate();
}

function renderMessage(role, text, { pending = false, error = false } = {}) {
  const el = document.createElement("div");
  el.className = `message ${role}${pending ? " pending" : ""}${error ? " error" : ""}`;
  el.textContent = text;
  messagesEl.appendChild(el);
  messagesEl.scrollTop = messagesEl.scrollHeight;
  return el;
}

async function sendMessage(text) {
  history.push({ role: "user", content: text });
  renderMessage("user", text);

  const pendingEl = renderMessage("assistant", "Thinking…", { pending: true });
  sendBtn.disabled = true;

  try {
    const res = await fetch(`${window.API_BASE}/api/chat`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "X-Access-Code": accessCode,
      },
      body: JSON.stringify({ messages: history }),
    });

    const data = await res.json().catch(() => ({}));

    if (res.status === 401) {
      // Bad or revoked code — drop it, restore the unsent text, and send the
      // user back to the gate rather than silently losing their message.
      sessionStorage.removeItem(ACCESS_CODE_KEY);
      accessCode = "";
      history.pop();
      pendingEl.remove();
      messagesEl.lastElementChild?.remove(); // the echoed user bubble
      input.value = text;
      showGate(data.detail || "Invalid access code.");
      return;
    }

    if (!res.ok) {
      const detail = data.detail || `Request failed (${res.status})`;
      pendingEl.remove();
      renderMessage("assistant", detail, { error: true });
      return;
    }

    pendingEl.remove();
    renderMessage("assistant", data.reply);
    history.push({ role: "assistant", content: data.reply });
  } catch (err) {
    pendingEl.remove();
    renderMessage("assistant", "Network error — is the backend running?", { error: true });
  } finally {
    sendBtn.disabled = false;
  }
}

form.addEventListener("submit", (e) => {
  e.preventDefault();
  const text = input.value.trim();
  if (!text) return;
  input.value = "";
  sendMessage(text);
});
