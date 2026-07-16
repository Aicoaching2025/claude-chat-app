const messagesEl = document.getElementById("messages");
const form = document.getElementById("composer");
const input = document.getElementById("input");
const sendBtn = document.getElementById("send-btn");

// Plain {role, content} history — this is the entire client-side state.
// The server re-derives any tool-use bookkeeping fresh on every turn.
const history = [];

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
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ messages: history }),
    });

    const data = await res.json().catch(() => ({}));

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
