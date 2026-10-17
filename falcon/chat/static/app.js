/**
 * HarshGuruJi Chat — Real-Time Client Application
 * WebSocket event reconciliation, live ranked search, and 4K responsive rendering.
 * Developed by: HarshGuruJi | https://www.webguruji.online
 */

const STATE = {
  currentUser: {
    id: "user_harsh_patel",
    username: "harshguruji",
    hgj_id: "HGJ-7F42K9",
    display_name: "Harsh Patel (HarshGuruJi)",
    avatar_url: "https://www.webguruji.online/logo-512.png"
  },
  activeConversation: null,
  conversations: [],
  messages: [],
  ws: null,
  searchTimer: null,
  isStartupEnabled: false
};

// ==================== INITIALIZATION ====================

document.addEventListener("DOMContentLoaded", async () => {
  initCurrentUser();
  initWebSocket();
  await loadConversations();
  await checkStartupStatus();
  setupEventListeners();
});

function initCurrentUser() {
  document.getElementById("userDisplayName").textContent = STATE.currentUser.display_name;
  document.getElementById("userHgjId").textContent = STATE.currentUser.hgj_id;
  document.getElementById("userAvatar").src = STATE.currentUser.avatar_url;
}

// ==================== WEBSOCKET HANDLING ====================

function initWebSocket() {
  const protocol = window.location.protocol === "https:" ? "wss:" : "ws:";
  const wsUrl = `${protocol}//${window.location.host}/ws/chat?user_id=${STATE.currentUser.id}`;

  try {
    STATE.ws = new WebSocket(wsUrl);

    STATE.ws.onopen = () => {
      console.log("[WS] Connected to HarshGuruJi Chat Realtime Engine");
      document.getElementById("connectionBeacon").classList.add("status-online");
      document.getElementById("connectionBeacon").classList.remove("status-offline");
    };

    STATE.ws.onmessage = (event) => {
      try {
        const payload = JSON.parse(event.data);
        handleWsEvent(payload.event, payload.data);
      } catch (e) {
        console.error("[WS] Parse error:", e);
      }
    };

    STATE.ws.onclose = () => {
      console.warn("[WS] Disconnected. Reconnecting in 3 seconds...");
      document.getElementById("connectionBeacon").classList.remove("status-online");
      document.getElementById("connectionBeacon").classList.add("status-offline");
      setTimeout(initWebSocket, 3000);
    };

    STATE.ws.onerror = (err) => {
      console.error("[WS] Socket error:", err);
    };
  } catch (err) {
    console.error("[WS] Initialization error:", err);
  }
}

function handleWsEvent(event, data) {
  if (event === "message:new") {
    // If message belongs to active conversation
    if (STATE.activeConversation && data.conversation_id === STATE.activeConversation.id) {
      appendMessageToView(data);
      scrollToBottom();
      // Mark as seen if receiver is viewing
      if (data.receiver_id === STATE.currentUser.id) {
        ackMessageStatus([data.id], "seen");
      }
    }
    // Refresh conversation list to show latest snippet and unread counter
    loadConversations();
  } else if (event === "message:seen" || event === "message:delivered") {
    updateMessageStatusInDom(data.message_id, data.status);
  } else if (event === "user:typing") {
    if (STATE.activeConversation && data.conversation_id === STATE.activeConversation.id) {
      showTypingIndicator(data.is_typing);
    }
  } else if (event === "user:presence") {
    updateUserPresence(data.user_id, data.is_online);
  }
}

// ==================== REST APIS & DATA ====================

async function loadConversations() {
  try {
    const res = await fetch(`/api/conversations?user_id=${STATE.currentUser.id}`);
    if (res.ok) {
      STATE.conversations = await res.json();
      renderConversationList();
    }
  } catch (e) {
    console.error("Failed to load conversations:", e);
  }
}

function renderConversationList() {
  const container = document.getElementById("conversationList");
  container.innerHTML = "";

  if (STATE.conversations.length === 0) {
    container.innerHTML = `
      <div style="text-align: center; padding: 30px; color: var(--text-dim);">
        <p>No conversations yet.</p>
        <p style="font-size: 12px; margin-top: 6px;">Search a username or HarshGuruJi ID above to start chatting!</p>
      </div>
    `;
    return;
  }

  STATE.conversations.forEach((conv) => {
    const isActive = STATE.activeConversation && STATE.activeConversation.id === conv.id;
    const item = document.createElement("div");
    item.className = `conv-item ${isActive ? "active" : ""}`;
    item.onclick = () => selectConversation(conv);

    const timeStr = conv.last_message_at ? formatTime(conv.last_message_at) : "";
    const preview = conv.last_message || "No messages yet";
    const unreadHtml = conv.unread_count > 0 ? `<span class="unread-badge">${conv.unread_count}</span>` : "";

    item.innerHTML = `
      <div class="avatar-wrapper">
        <img class="avatar-img" src="${conv.partner_avatar_url || 'https://www.webguruji.online/logo-192.png'}" alt="Avatar">
        <span class="status-indicator ${conv.partner_is_online ? 'status-online' : 'status-offline'}"></span>
      </div>
      <div class="conv-body">
        <div class="conv-top">
          <span class="conv-name">${escapeHtml(conv.partner_display_name)}</span>
          <span class="conv-time">${timeStr}</span>
        </div>
        <div class="conv-bottom">
          <span class="conv-preview">${escapeHtml(preview)}</span>
          ${unreadHtml}
        </div>
      </div>
    `;
    container.appendChild(item);
  });
}

async function selectConversation(conv) {
  STATE.activeConversation = conv;
  renderConversationList();

  // Show active chat panel
  document.getElementById("emptyChatState").style.display = "none";
  document.getElementById("activeChatContent").style.display = "flex";

  // Set header details
  document.getElementById("partnerAvatar").src = conv.partner_avatar_url || "https://www.webguruji.online/logo-192.png";
  document.getElementById("partnerName").textContent = conv.partner_display_name;
  document.getElementById("partnerMeta").innerHTML = `
    <span>@${conv.partner_username}</span>
    <span>•</span>
    <span style="color: var(--accent-cyan);">${conv.partner_hgj_id}</span>
  `;

  // Load message history
  await loadMessages(conv.id);

  // Acknowledge unread messages as 'seen'
  const unreadIds = STATE.messages
    .filter(m => m.receiver_id === STATE.currentUser.id && m.status !== "seen")
    .map(m => m.id);
  if (unreadIds.length > 0) {
    ackMessageStatus(unreadIds, "seen");
  }
}

async function loadMessages(convId) {
  try {
    const res = await fetch(`/api/conversations/${convId}/messages?user_id=${STATE.currentUser.id}&limit=100`);
    if (res.ok) {
      STATE.messages = await res.json();
      renderMessageHistory();
      scrollToBottom();
    }
  } catch (e) {
    console.error("Failed to fetch messages:", e);
  }
}

function renderMessageHistory() {
  const container = document.getElementById("messageHistory");
  container.innerHTML = "";

  if (STATE.messages.length === 0) {
    container.innerHTML = `
      <div style="text-align: center; margin: auto; color: var(--text-dim);">
        <p>No messages yet.</p>
        <p style="font-size: 13px; margin-top: 4px;">Say hi to start the conversation! 👋</p>
      </div>
    `;
    return;
  }

  let lastDate = "";
  STATE.messages.forEach((msg) => {
    const msgDate = formatDate(msg.created_at);
    if (msgDate !== lastDate) {
      lastDate = msgDate;
      const sep = document.createElement("div");
      sep.className = "date-separator";
      sep.innerHTML = `<span>${msgDate}</span>`;
      container.appendChild(sep);
    }

    const isSender = msg.sender_id === STATE.currentUser.id;
    const row = document.createElement("div");
    row.className = `message-row ${isSender ? "sender" : "receiver"}`;
    row.id = `msg-${msg.id}`;

    // WhatsApp style tick marks
    let statusTicks = "";
    if (isSender) {
      if (msg.status === "seen") {
        statusTicks = `<span class="status-ticks seen">✓✓</span>`;
      } else if (msg.status === "delivered") {
        statusTicks = `<span class="status-ticks">✓✓</span>`;
      } else {
        statusTicks = `<span class="status-ticks">✓</span>`;
      }
    }

    row.innerHTML = `
      <div class="message-bubble">
        <div class="message-text">${escapeHtml(msg.content)}</div>
        <div class="message-meta">
          <span>${formatTime(msg.created_at)}</span>
          ${statusTicks}
        </div>
      </div>
      <div class="bubble-actions">
        <button class="action-btn" title="Delete for me" onclick="deleteMessage('${msg.id}', false)">🗑️ Me</button>
        ${isSender ? `<button class="action-btn" title="Delete for everyone" onclick="deleteMessage('${msg.id}', true)">❌ All</button>` : ""}
      </div>
    `;
    container.appendChild(row);
  });
}

function appendMessageToView(msg) {
  STATE.messages.push(msg);
  const container = document.getElementById("messageHistory");
  const isSender = msg.sender_id === STATE.currentUser.id;

  const row = document.createElement("div");
  row.className = `message-row ${isSender ? "sender" : "receiver"}`;
  row.id = `msg-${msg.id}`;

  let statusTicks = isSender ? `<span class="status-ticks">✓</span>` : "";
  row.innerHTML = `
    <div class="message-bubble">
      <div class="message-text">${escapeHtml(msg.content)}</div>
      <div class="message-meta">
        <span>${formatTime(msg.created_at || new Date().toISOString())}</span>
        ${statusTicks}
      </div>
    </div>
  `;
  container.appendChild(row);
}

// ==================== SEND MESSAGE ====================

async function sendMessage(e) {
  if (e) e.preventDefault();
  const input = document.getElementById("messageInput");
  const content = input.value.trim();
  if (!content || !STATE.activeConversation) return;

  const idempotencyKey = "idemp_" + Date.now() + "_" + Math.random().toString(36).substr(2, 6);
  input.value = "";

  try {
    const res = await fetch(`/api/conversations/${STATE.activeConversation.id}/messages?user_id=${STATE.currentUser.id}`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        content: content,
        idempotency_key: idempotencyKey
      })
    });
    if (!res.ok) {
      const err = await res.json();
      alert("Error sending message: " + (err.detail || "Forbidden"));
    }
  } catch (err) {
    console.error("Failed to send message:", err);
  }
}

async function ackMessageStatus(messageIds, status) {
  try {
    await fetch(`/api/messages/status?user_id=${STATE.currentUser.id}`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ message_ids: messageIds, status: status })
    });
  } catch (e) {
    console.debug("Ack status notice:", e);
  }
}

async function deleteMessage(msgId, deleteForEveryone) {
  if (!confirm(`Are you sure you want to delete this message ${deleteForEveryone ? 'for everyone' : 'for yourself'}?`)) return;

  try {
    const res = await fetch(`/api/messages/${msgId}?user_id=${STATE.currentUser.id}&everyone=${deleteForEveryone}`, {
      method: "DELETE"
    });
    if (res.ok) {
      if (deleteForEveryone) {
        const bubble = document.querySelector(`#msg-${msgId} .message-text`);
        if (bubble) bubble.textContent = "[This message was deleted]";
      } else {
        const row = document.getElementById(`msg-${msgId}`);
        if (row) row.remove();
      }
    }
  } catch (e) {
    console.error("Delete error:", e);
  }
}

// ==================== USER SEARCH ====================

function handleSearchInput(e) {
  const query = e.target.value.trim();
  clearTimeout(STATE.searchTimer);

  if (!query) {
    document.getElementById("searchSuggestions").style.display = "none";
    return;
  }

  STATE.searchTimer = setTimeout(async () => {
    try {
      const res = await fetch(`/api/search?q=${encodeURIComponent(query)}&user_id=${STATE.currentUser.id}`);
      if (res.ok) {
        const results = await res.json();
        renderSearchSuggestions(results);
      }
    } catch (err) {
      console.error("Search error:", err);
    }
  }, 200);
}

function renderSearchSuggestions(results) {
  const container = document.getElementById("searchSuggestions");
  container.innerHTML = "";

  if (results.length === 0) {
    container.innerHTML = `<div style="padding: 14px; text-align: center; color: var(--text-dim); font-size: 13px;">No accounts found</div>`;
    container.style.display = "block";
    return;
  }

  results.forEach(user => {
    const item = document.createElement("div");
    item.className = "suggestion-item";
    item.onclick = () => selectSearchResult(user);

    item.innerHTML = `
      <img src="${user.avatar_url || 'https://www.webguruji.online/logo-192.png'}" style="width: 36px; height: 36px; border-radius: 50%;" alt="">
      <div class="suggestion-info">
        <div class="suggestion-name">${escapeHtml(user.display_name)}</div>
        <div class="suggestion-meta">
          <span>@${user.username}</span>
          <span>•</span>
          <span class="suggestion-id">${user.hgj_id}</span>
        </div>
      </div>
      <span class="status-indicator ${user.is_online ? 'status-online' : 'status-offline'}" style="position: static; width: 8px; height: 8px;"></span>
    `;
    container.appendChild(item);
  });
  container.style.display = "block";
}

async function selectSearchResult(user) {
  document.getElementById("searchSuggestions").style.display = "none";
  document.getElementById("searchInput").value = "";

  try {
    const res = await fetch(`/api/conversations?partner_id=${user.id}&user_id=${STATE.currentUser.id}`, {
      method: "POST"
    });
    if (res.ok) {
      const conv = await res.json();
      await loadConversations();
      // Find loaded conversation with partner details
      const found = STATE.conversations.find(c => c.id === conv.id) || {
        ...conv,
        partner_display_name: user.display_name,
        partner_username: user.username,
        partner_hgj_id: user.hgj_id,
        partner_avatar_url: user.avatar_url,
        partner_is_online: user.is_online
      };
      selectConversation(found);
    }
  } catch (e) {
    console.error("Start chat error:", e);
  }
}

// ==================== BLOCKING ====================

async function toggleBlockUser() {
  if (!STATE.activeConversation) return;
  const partnerId = STATE.activeConversation.partner_id;
  const partnerName = STATE.activeConversation.partner_display_name;

  if (!confirm(`Are you sure you want to block ${partnerName}? You will not be able to send or receive messages from this user.`)) return;

  try {
    const res = await fetch(`/api/blocks?user_id=${STATE.currentUser.id}`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ target_id: partnerId })
    });
    if (res.ok) {
      alert(`User ${partnerName} has been blocked.`);
      await loadConversations();
      document.getElementById("activeChatContent").style.display = "none";
      document.getElementById("emptyChatState").style.display = "block";
    }
  } catch (e) {
    console.error("Block error:", e);
  }
}

// ==================== WINDOWS STARTUP TOGGLE ====================

async function checkStartupStatus() {
  try {
    const res = await fetch("/api/system/startup");
    if (res.ok) {
      const data = await res.json();
      STATE.isStartupEnabled = data.is_enabled;
      updateStartupButton(data.is_enabled);
    }
  } catch (e) {
    console.debug("Startup status query note:", e);
  }
}

async function toggleStartup() {
  const newAction = STATE.isStartupEnabled ? "disable" : "enable";
  try {
    const res = await fetch("/api/system/startup", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ action: newAction })
    });
    if (res.ok) {
      const data = await res.json();
      STATE.isStartupEnabled = data.is_enabled;
      updateStartupButton(data.is_enabled);
      const msg = data.is_enabled ? "Falcon will now launch on Windows Startup! 🚀" : "Falcon removed from Windows Startup.";
      alert(msg);
    }
  } catch (e) {
    console.error("Toggle startup failed:", e);
  }
}

function updateStartupButton(enabled) {
  const btn = document.getElementById("startupToggleBtn");
  if (enabled) {
    btn.classList.add("active");
    btn.innerHTML = `<span>⚡ Windows Startup: ON</span>`;
  } else {
    btn.classList.remove("active");
    btn.innerHTML = `<span>⚡ Windows Startup: OFF</span>`;
  }
}

// ==================== HELPERS ====================

function setupEventListeners() {
  document.getElementById("searchInput").addEventListener("input", handleSearchInput);
  document.getElementById("composerForm").addEventListener("submit", sendMessage);
  document.getElementById("startupToggleBtn").addEventListener("click", toggleStartup);
  document.getElementById("blockUserBtn").addEventListener("click", toggleBlockUser);

  // Close suggestions when clicking outside
  document.addEventListener("click", (e) => {
    if (!e.target.closest(".search-container")) {
      document.getElementById("searchSuggestions").style.display = "none";
    }
  });
}

function updateMessageStatusInDom(msgId, newStatus) {
  const row = document.getElementById(`msg-${msgId}`);
  if (row) {
    const ticks = row.querySelector(".status-ticks");
    if (ticks) {
      if (newStatus === "seen") {
        ticks.className = "status-ticks seen";
        ticks.textContent = "✓✓";
      } else if (newStatus === "delivered") {
        ticks.className = "status-ticks";
        ticks.textContent = "✓✓";
      }
    }
  }
}

function showTypingIndicator(isTyping) {
  const el = document.getElementById("typingIndicator");
  el.style.display = isTyping ? "flex" : "none";
  if (isTyping) scrollToBottom();
}

function updateUserPresence(userId, isOnline) {
  if (STATE.activeConversation && STATE.activeConversation.partner_id === userId) {
    const indicator = document.getElementById("partnerOnlineBeacon");
    if (indicator) {
      indicator.className = `status-indicator ${isOnline ? 'status-online' : 'status-offline'}`;
    }
  }
}

function scrollToBottom() {
  const history = document.getElementById("messageHistory");
  history.scrollTop = history.scrollHeight;
}

function formatTime(isoStr) {
  try {
    const d = new Date(isoStr);
    return d.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
  } catch (e) {
    return "";
  }
}

function formatDate(isoStr) {
  try {
    const d = new Date(isoStr);
    const today = new Date();
    if (d.toDateString() === today.toDateString()) return "Today";
    const yesterday = new Date(today);
    yesterday.setDate(today.getDate() - 1);
    if (d.toDateString() === yesterday.toDateString()) return "Yesterday";
    return d.toLocaleDateString([], { month: 'short', day: 'numeric', year: 'numeric' });
  } catch (e) {
    return "";
  }
}

function escapeHtml(text) {
  if (!text) return "";
  const map = { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#039;' };
  return text.replace(/[&<>"']/g, m => map[m]);
}
