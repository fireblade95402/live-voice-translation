const newConversationButton = document.getElementById("newConversation");
const statusEl = document.getElementById("status");
const chatEl = document.getElementById("chat");

let conversationActive = false;
let socket;
let currentUserMessage = null;
let currentAssistantMessage = null;

function setStatus(message) {
  statusEl.textContent = message;
}

function clearConversation() {
  chatEl.innerHTML = "";
  currentUserMessage = null;
  currentAssistantMessage = null;
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

function startConversation() {
  if (!socket || socket.readyState !== WebSocket.OPEN) {
    setStatus("Waiting for connection...");
    return;
  }
  conversationActive = true;
  clearConversation();
  setStatus("Starting session...");
  console.log("Sending start message");
  socket.send(JSON.stringify({ type: "start", text: "Hi" }));
}

function stopConversation() {
  conversationActive = false;
  setStatus("Idle");
  if (socket && socket.readyState === WebSocket.OPEN) {
    socket.send(JSON.stringify({ type: "stop" }));
  }
}

newConversationButton.addEventListener("click", () => {
  if (conversationActive) {
    stopConversation();
  }
  startConversation();
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
  });

  socket.addEventListener("close", () => {
    console.log("WebSocket closed");
    setStatus("Disconnected");
  });

  socket.addEventListener("error", (event) => {
    console.error("WebSocket error:", event);
    setStatus("Connection error");
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
connectWebSocket();
