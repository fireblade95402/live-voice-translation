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
let audioContext = null;
let audioWorklet = null;
let mediaStream = null;
let audioProcessor = null;
let audioQueue = [];
let isPlayingAudio = false;
let nextPlayTime = 0;

function setStatus(message) {
  statusEl.textContent = message;
}

// Map common language names to representative country codes (fallbacks)
const languageToCountry = {
  English: "gb",
  Spanish: "es",
  French: "fr",
  German: "de",
  Italian: "it",
  Chinese: "cn",
  Japanese: "jp",
  Korean: "kr",
  Portuguese: "pt",
  Russian: "ru",
  Arabic: "sa",
  Hindi: "in"
};

function countryCodeToEmoji(code) {
  if (!code || code.length !== 2) return null;
  const A = 0x1f1e6;
  const chars = code.toUpperCase().split("");
  return String.fromCodePoint(...chars.map(c => A + c.charCodeAt(0) - 65));
}

function makeCombinedFlagSVG(lang1, lang2) {
  // Resolve emojis (use initials fallback if unknown)
  const code1 = languageToCountry[lang1] || null;
  const code2 = languageToCountry[lang2] || null;
  const emoji1 = code1 ? countryCodeToEmoji(code1) : (lang1 ? lang1.slice(0,2).toUpperCase() : "");
  const emoji2 = code2 ? countryCodeToEmoji(code2) : (lang2 ? lang2.slice(0,2).toUpperCase() : "");

  const svg = `<?xml version='1.0' encoding='UTF-8'?>
  <svg xmlns='http://www.w3.org/2000/svg' width='160' height='90' viewBox='0 0 160 90'>
    <rect width='160' height='90' rx='8' fill='rgba(0,0,0,0.06)' />
    <rect x='6' y='6' width='72' height='78' rx='6' fill='white' />
    <rect x='82' y='6' width='72' height='78' rx='6' fill='white' />
    <text x='42' y='54' font-size='44' text-anchor='middle' dominant-baseline='middle'>${emoji1}</text>
    <text x='122' y='54' font-size='44' text-anchor='middle' dominant-baseline='middle'>${emoji2}</text>
  </svg>`;

  return 'data:image/svg+xml;utf8,' + encodeURIComponent(svg);
}

function updateCombinedFlag(lang1, lang2) {
  try {
    const uri = makeCombinedFlagSVG(lang1 || "", lang2 || "");
    languageDisplayEl.style.backgroundImage = `url("${uri}")`;
  } catch (e) {
    console.error('Failed to generate combined flag SVG', e);
    languageDisplayEl.style.backgroundImage = '';
  }
}

function clearConversation() {
  chatEl.innerHTML = "";
  currentUserMessage = null;
  currentAssistantMessage = null;
}

function hideLanguages() {
  languageDisplayEl.style.display = "none";
  languages = { lang1: null, lang2: null };
}

function playAudio(audioDataBase64) {
  if (!audioContext) {
    console.warn("Audio context not initialized");
    return;
  }

  try {
    // Decode base64 to binary
    const binaryString = atob(audioDataBase64);
    const bytes = new Uint8Array(binaryString.length);
    for (let i = 0; i < binaryString.length; i++) {
      bytes[i] = binaryString.charCodeAt(i);
    }

    // Create AudioBuffer from PCM16 data (24kHz, mono)
    const sampleRate = 24000;
    const numSamples = bytes.length / 2; // 16-bit = 2 bytes per sample
    const audioBuffer = audioContext.createBuffer(1, numSamples, sampleRate);
    const channelData = audioBuffer.getChannelData(0);
    
    // Convert bytes to float32
    const view = new DataView(bytes.buffer);
    for (let i = 0; i < numSamples; i++) {
      const int16 = view.getInt16(i * 2, true); // true for little-endian
      channelData[i] = int16 / 32768.0; // Normalize to -1..1
    }

    // Add to queue instead of playing immediately
    audioQueue.push(audioBuffer);
    
    // Start playing if not already playing
    if (!isPlayingAudio) {
      playNextAudioChunk();
    }
  } catch (error) {
    console.error("Error playing audio:", error);
  }
}

function playNextAudioChunk() {
  if (audioQueue.length === 0) {
    isPlayingAudio = false;
    return;
  }

  isPlayingAudio = true;
  const audioBuffer = audioQueue.shift();
  
  const source = audioContext.createBufferSource();
  source.buffer = audioBuffer;
  source.connect(audioContext.destination);
  
  // Calculate when to start this chunk
  const currentTime = audioContext.currentTime;
  const startTime = Math.max(currentTime, nextPlayTime);
  
  // Schedule the next chunk to play right after this one
  nextPlayTime = startTime + audioBuffer.duration;
  
  // When this chunk finishes, play the next one
  source.onended = () => {
    playNextAudioChunk();
  };
  
  source.start(startTime);
}

async function startMicrophoneCapture() {
  try {
    if (!audioContext) {
      audioContext = new (window.AudioContext || window.webkitAudioContext)();
    }

    console.log(`Audio context sample rate: ${audioContext.sampleRate}Hz`);

    // Request microphone access (browser will use its native sample rate)
    mediaStream = await navigator.mediaDevices.getUserMedia({ 
      audio: {
        channelCount: 1,
        echoCancellation: true,
        noiseSuppression: true,
        autoGainControl: true
      }
    });

    console.log("Microphone access granted");

    // Create audio nodes
    const source = audioContext.createMediaStreamSource(mediaStream);
    
    // Create ScriptProcessor for real-time audio processing (4096 is ~170ms at 24kHz, must be power of 2)
    audioProcessor = audioContext.createScriptProcessor(4096, 1, 1);
    
    let audioChunkCount = 0;
    const targetSampleRate = 24000; // Azure VoiceLive expects 24kHz
    const sourceSampleRate = audioContext.sampleRate;
    
    audioProcessor.onaudioprocess = (event) => {
      audioChunkCount++;
      if (audioChunkCount % 10 === 0) {
        console.log(`Processing audio chunk #${audioChunkCount}`);
      }
      
      const inputData = event.inputBuffer.getChannelData(0);
      
      // Resample if needed
      let resampledData;
      if (sourceSampleRate !== targetSampleRate) {
        // Simple linear resampling
        const ratio = targetSampleRate / sourceSampleRate;
        const outputLength = Math.floor(inputData.length * ratio);
        resampledData = new Float32Array(outputLength);
        
        for (let i = 0; i < outputLength; i++) {
          const srcIndex = i / ratio;
          const srcIndexFloor = Math.floor(srcIndex);
          const srcIndexCeil = Math.min(srcIndexFloor + 1, inputData.length - 1);
          const fraction = srcIndex - srcIndexFloor;
          
          resampledData[i] = inputData[srcIndexFloor] * (1 - fraction) + inputData[srcIndexCeil] * fraction;
        }
      } else {
        resampledData = inputData;
      }
      
      // Convert float32 to PCM16
      const pcm16Data = new Int16Array(resampledData.length);
      for (let i = 0; i < resampledData.length; i++) {
        let s = Math.max(-1, Math.min(1, resampledData[i]));
        pcm16Data[i] = s < 0 ? s * 0x8000 : s * 0x7FFF;
      }
      
      // Convert to base64
      const uint8Data = new Uint8Array(pcm16Data.buffer);
      let binaryString = '';
      for (let i = 0; i < uint8Data.length; i++) {
        binaryString += String.fromCharCode(uint8Data[i]);
      }
      const audioBase64 = btoa(binaryString);
      
      // Send to server
      if (!conversationActive) {
        return; // Don't send if not active
      }
      
      if (conversationPaused) {
        return; // Don't send if paused
      }
      
      if (!socket) {
        console.warn("No socket available");
        return;
      }
      
      if (socket.readyState !== WebSocket.OPEN) {
        console.warn(`Socket not open: readyState=${socket.readyState}`);
        return;
      }
      
      try {
        socket.send(JSON.stringify({
          type: "audio",
          data: audioBase64
        }));
        if (audioChunkCount % 10 === 0) {
          console.log("Sent audio chunk");
        }
      } catch (error) {
        console.error("Error sending audio:", error);
      }
    };
    
    // IMPORTANT: ScriptProcessor needs to be connected to process audio
    // We use a disconnected destination (no actual playback) to avoid echo
    const destination = audioContext.createMediaStreamDestination();
    
    // Connect: source -> processor -> destination (NOT to speakers)
    source.connect(audioProcessor);
    audioProcessor.connect(destination);
    
    console.log("Microphone capture started");
  } catch (error) {
    console.error("Error accessing microphone:", error);
    setStatus("Microphone access denied");
  }
}

function stopMicrophoneCapture() {
  if (audioProcessor) {
    audioProcessor.disconnect();
    audioProcessor = null;
  }
  
  if (mediaStream) {
    mediaStream.getTracks().forEach(track => track.stop());
    mediaStream = null;
  }
  
  console.log("Microphone capture stopped");
}

function showLanguages(lang1, lang2) {
  languages.lang1 = lang1;
  languages.lang2 = lang2;
  language1El.textContent = lang1;
  language2El.textContent = lang2;
  languageDisplayEl.style.display = "flex";
  // Generate and set combined flag background whenever languages update
  updateCombinedFlag(lang1, lang2);
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
  
  // Scroll to bottom to show the latest message (iOS Safari compatible)
  scrollToBottom();
  
  return bubble;
}

function appendToMessage(bubble, text) {
  bubble.textContent += text;
  
  // Keep scrolled to bottom as text is appended
  scrollToBottom();
}

function scrollToBottom() {
  // Use multiple methods to ensure iOS Safari scrolls correctly
  requestAnimationFrame(() => {
    chatEl.scrollTop = chatEl.scrollHeight;
    
    // Force another scroll after a brief delay for iOS Safari
    setTimeout(() => {
      chatEl.scrollTop = chatEl.scrollHeight;
    }, 10);
  });
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

  // Start microphone capture
  startMicrophoneCapture();

  const payload = { type: "start" };
  if (typeof initialText === "string") {
    payload.text = initialText;
  }
  socket.send(JSON.stringify(payload));
}

function stopConversation({ setIdle = true } = {}) {
  // Stop microphone capture
  stopMicrophoneCapture();
  
  // Clear audio playback queue
  audioQueue = [];
  isPlayingAudio = false;
  nextPlayTime = 0;
  
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
    // Initialize audio context when WebSocket opens
    if (!audioContext) {
      audioContext = new (window.AudioContext || window.webkitAudioContext)();
    }
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
      case "audio":
        // Handle audio playback
        playAudio(data.data);
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
        if (data.text) {
          const extractedLangs = extractLanguages(data.text);
          console.log("Extracted languages:", extractedLangs);
          if (extractedLangs) {
            // Update the UI if languages changed during the conversation
            if (
              extractedLangs.lang1 !== languages.lang1 ||
              extractedLangs.lang2 !== languages.lang2
            ) {
              showLanguages(extractedLangs.lang1, extractedLangs.lang2);
            }
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
