const newConversationButton = document.getElementById("newConversation");
const pauseConversationButton = document.getElementById("pauseConversation");
const statusEl = document.getElementById("status");
const chatEl = document.getElementById("chat");
const languageDisplayEl = document.getElementById("languageDisplay");
const language1El = document.getElementById("language1");
const language2El = document.getElementById("language2");

let conversationActive = false;
let conversationPaused = false;
let socket;
let currentUserMessage = null;
let currentAssistantMessage = null;
let languages = { lang1: null, lang2: null };

function setStatus(message) {
  statusEl.textContent = message;
}

function clearConversation() {
  chatEl.innerHTML = "";
  currentUserMessage = null;
  currentAssistantMessage = null;
  hideLanguages();
}

function hideLanguages() {
  languageDisplayEl.style.display = "none";
  languages = { lang1: null, lang2: null };
}

function showLanguages(lang1, lang2) {
  languages.lang1 = lang1;
  languages.lang2 = lang2;
  language1El.textContent = lang1;
  language2El.textContent = lang2;
  languageDisplayEl.style.display = "flex";
}

function extractLanguages(text) {
  // Pattern: "I will translate between [Language1] and [Language2]"
  const pattern = /translate between ([A-Za-z\s]+) and ([A-Za-z\s]+)/i;
  const match = text.match(pattern);
  
  if (match) {
    return {
      lang1: match[1].trim(),
      lang2: match[2].trim()
    };
  }
  return null;
}

function addMessage(role, text) {
  const messageDiv = document.createElement("div");
  messageDiv.className = `message ${role}`;
  
  const bubble = document.createElement("div");
  bubble.className = `bubble ${role}`;
  bubble.textContent = text;
  
  messageDiv.appendChild(bubble);
  chatEl.appendChild(messageDiv);
  chatEl.scrollTop = chatEl.scrollHeight;
  
  return bubble;
}

function appendToMessage(bubble, text) {
  bubble.textContent += text;
  chatEl.scrollTop = chatEl.scrollHeight;
}

function updateControls() {
  if (!conversationActive) {
    pauseConversationButton.disabled = true;
    pauseConversationButton.textContent = "Pause";
    return;
  }

  pauseConversationButton.disabled = false;
  pauseConversationButton.textContent = conversationPaused ? "Resume" : "Pause";
}

function startConversation({ clear = true, initialText, statusMessage } = {}) {
  if (!socket || socket.readyState !== WebSocket.OPEN) {
    setStatus("Waiting for connection...");
    return;
  }
  conversationActive = true;
  conversationPaused = false;
  if (clear) {
    clearConversation();
  }
  setStatus(statusMessage || "Starting session...");
  updateControls();
  console.log("Sending start message");

  const payload = { type: "start" };
  if (typeof initialText === "string") {
    payload.text = initialText;
  }
  socket.send(JSON.stringify(payload));
}

function stopConversation({ setIdle = true } = {}) {
  if (setIdle) {
    conversationActive = false;
    conversationPaused = false;
    setStatus("Idle");
  }
  updateControls();
  if (socket && socket.readyState === WebSocket.OPEN) {
    socket.send(JSON.stringify({ type: "stop" }));
  }
}

function pauseConversation() {
  if (!conversationActive || conversationPaused) {
    return;
  }
  conversationPaused = true;
  setStatus("Paused");
  updateControls();
  stopConversation({ setIdle: false });
}

function resumeConversation() {
  if (!conversationActive || !conversationPaused) {
    return;
  }
  conversationPaused = false;
  startConversation({ clear: false, statusMessage: "Resuming session..." });
}

newConversationButton.addEventListener("click", () => {
  if (conversationActive) {
    stopConversation();
  }
  startConversation({ initialText: "Hi" });
});

pauseConversationButton.addEventListener("click", () => {
  if (!conversationActive) {
    return;
  }
  if (conversationPaused) {
    resumeConversation();
  } else {
    pauseConversation();
  }
});

function appendText(el, text) {
  el.textContent += text;
  el.scrollTop = el.scrollHeight;
}

function connectWebSocket() {
  const protocol = window.location.protocol === "https:" ? "wss" : "ws";
  const url = `${protocol}://${window.location.host}/ws`;
  console.log("Connecting to:", url);
  socket = new WebSocket(url);

  socket.addEventListener("open", () => {
    console.log("WebSocket connected");
    setStatus("Connected");
    updateControls();
  });

  socket.addEventListener("close", () => {
    console.log("WebSocket closed");
    setStatus("Disconnected");
    conversationActive = false;
    conversationPaused = false;
    updateControls();
  });

  socket.addEventListener("error", (event) => {
    console.error("WebSocket error:", event);
    setStatus("Connection error");
    conversationActive = false;
    conversationPaused = false;
    updateControls();
  });

  socket.addEventListener("message", (event) => {
    console.log("Message received:", event.data);
    const data = JSON.parse(event.data);
    switch (data.type) {
      case "status":
        setStatus(data.message);
        break;
      case "transcript_delta":
        if (!currentUserMessage) {
          currentUserMessage = addMessage("user", "");
        }
        appendToMessage(currentUserMessage, data.text || "");
        break;
      case "transcript_done":
        currentUserMessage = null;
        break;
      case "assistant_delta":
        if (!currentAssistantMessage) {
          currentAssistantMessage = addMessage("assistant", "");
        }
        appendToMessage(currentAssistantMessage, data.text || "");
        break;
      case "assistant_done":
        // Check if this message contains language confirmation
        console.log("Checking for languages in:", data.text);
        if (data.text && !languages.lang1) {
          const extractedLangs = extractLanguages(data.text);
          console.log("Extracted languages:", extractedLangs);
          if (extractedLangs) {
            showLanguages(extractedLangs.lang1, extractedLangs.lang2);
          }
        }
        currentAssistantMessage = null;
        break;
      case "error":
        setStatus("Error: " + (data.message || "Unknown error"));
        break;
      default:
        break;
    }
  });
}

setStatus("Connecting...");
updateControls();
connectWebSocket();
