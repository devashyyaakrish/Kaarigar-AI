/* ===== Karigar AI — Frontend Logic ===== */

const API = '';   // same origin

/* ---- Helpers ---- */
function ts() {
  return new Date().toLocaleTimeString('en-IN', { hour: '2-digit', minute: '2-digit', hour12: true });
}

function formatText(text) {
  // Convert *bold* → <strong>
  return text
    .replace(/\*(.*?)\*/g, '<strong>$1</strong>')
    .replace(/\n/g, '<br>');
}

function addBubble(chatId, text, isUser = false) {
  const chat = document.getElementById(chatId);
  if (!chat) return;

  const div = document.createElement('div');
  div.className = `chat-bubble ${isUser ? 'user-bubble' : 'bot-bubble'}`;
  div.innerHTML = `${formatText(text)}<span class="ts">${ts()}</span>`;
  chat.appendChild(div);
  chat.scrollTop = chat.scrollHeight;
  return div;
}

function showTyping(chatId) {
  const chat = document.getElementById(chatId);
  const div = document.createElement('div');
  div.className = 'typing-bubble';
  div.id = `typing-${chatId}`;
  div.innerHTML = '<div class="typing-dots"><span></span><span></span><span></span></div>';
  chat.appendChild(div);
  chat.scrollTop = chat.scrollHeight;
}

function removeTyping(chatId) {
  const el = document.getElementById(`typing-${chatId}`);
  if (el) el.remove();
}

function setStatus(msg) {
  document.getElementById('status-text').textContent = msg;
}

function flashStep(stepId) {
  const steps = ['step-analyze', 'step-match', 'step-ping', 'step-verify'];
  steps.forEach(s => document.getElementById(s)?.classList.remove('active'));
  const el = document.getElementById(stepId);
  if (el) {
    el.classList.add('active');
    setTimeout(() => el.classList.remove('active'), 2500);
  }
}

/* ---- Customer message ---- */
async function sendCustomerMessage() {
  const input = document.getElementById('customer-input');
  const message = input.value.trim();
  if (!message) return;

  addBubble('customer-chat', message, true);
  input.value = '';
  setStatus('Analyzing your message...');
  showTyping('customer-chat');
  flashStep('step-analyze');

  try {
    const res = await fetch(`${API}/api/customer/message`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ message })
    });
    const data = await res.json();
    removeTyping('customer-chat');

    if (data.customer_reply) {
      addBubble('customer-chat', data.customer_reply);
    }
    if (data.worker_reply) {
      showTyping('worker-chat');
      flashStep('step-ping');
      setTimeout(() => {
        removeTyping('worker-chat');
        addBubble('worker-chat', data.worker_reply);
      }, 800);
    }
    if (data.workers_found) {
      flashStep('step-match');
      setStatus(`Found ${data.workers_found} workers! Customer is selecting...`);
    } else {
      setStatus('Ready');
    }
  } catch (err) {
    removeTyping('customer-chat');
    addBubble('customer-chat', '⚠️ Error connecting to server. Is the server running?');
    setStatus('Error — check server');
    console.error(err);
  }
}

/* ---- Customer image ---- */
async function sendCustomerImage() {
  const fileInput = document.getElementById('customer-image-input');
  const file = fileInput.files[0];
  if (!file) return;

  addBubble('customer-chat', `📷 Photo sent: ${file.name}`, true);
  setStatus('AI analyzing your photo...');
  showTyping('customer-chat');
  flashStep('step-analyze');

  const formData = new FormData();
  formData.append('image', file);
  formData.append('message', '');
  fileInput.value = '';

  try {
    const res = await fetch(`${API}/api/customer/image`, {
      method: 'POST',
      body: formData
    });
    const data = await res.json();
    removeTyping('customer-chat');

    if (data.analysis) {
      const a = data.analysis;
      addBubble('customer-chat',
        `🔍 *Detected:* ${a.problem_type} — ${a.specific_issue}\n` +
        `📊 Severity: ${a.severity} | ⚡ Urgency: ${a.urgency}`
      );
      flashStep('step-match');
    }
    if (data.customer_reply) {
      setTimeout(() => addBubble('customer-chat', data.customer_reply), 400);
    }
    if (data.worker_reply) {
      showTyping('worker-chat');
      flashStep('step-ping');
      setTimeout(() => {
        removeTyping('worker-chat');
        addBubble('worker-chat', data.worker_reply);
      }, 1000);
    }
    setStatus(data.workers_found ? `Found ${data.workers_found} workers!` : 'Ready');
  } catch (err) {
    removeTyping('customer-chat');
    addBubble('customer-chat', '⚠️ Error uploading image.');
    setStatus('Error');
    console.error(err);
  }
}

/* ---- Worker message ---- */
async function sendWorkerMessage() {
  const input = document.getElementById('worker-input');
  const message = input.value.trim();
  if (!message) return;

  addBubble('worker-chat', message, true);
  input.value = '';
  setStatus('Worker responded...');
  showTyping('worker-chat');

  try {
    const res = await fetch(`${API}/api/worker/message`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ message })
    });
    const data = await res.json();
    removeTyping('worker-chat');

    if (data.worker_reply) addBubble('worker-chat', data.worker_reply);
    if (data.customer_reply) {
      showTyping('customer-chat');
      setTimeout(() => {
        removeTyping('customer-chat');
        addBubble('customer-chat', data.customer_reply);
      }, 600);
    }

    // Handle specific responses
    if (data.reassigned_to) {
      setStatus(`Job reassigned → ${data.reassigned_to}`);
      flashStep('step-ping');
    } else if (data.worker_reply?.toLowerCase().includes('verified')) {
      flashStep('step-verify');
      setStatus('Job verified! Awaiting customer rating...');
    } else {
      setStatus('Ready');
    }
  } catch (err) {
    removeTyping('worker-chat');
    addBubble('worker-chat', '⚠️ Error connecting to server.');
    setStatus('Error');
    console.error(err);
  }
}

/* ---- Worker image (completion photo) ---- */
async function sendWorkerImage() {
  const fileInput = document.getElementById('worker-image-input');
  const file = fileInput.files[0];
  if (!file) return;

  addBubble('worker-chat', `📷 Completion photo: ${file.name}`, true);
  setStatus('AI verifying job completion...');
  showTyping('worker-chat');
  flashStep('step-verify');

  const formData = new FormData();
  formData.append('image', file);
  fileInput.value = '';

  try {
    const res = await fetch(`${API}/api/worker/image`, {
      method: 'POST',
      body: formData
    });
    const data = await res.json();
    removeTyping('worker-chat');

    if (data.worker_reply) addBubble('worker-chat', data.worker_reply);
    if (data.verification) {
      const v = data.verification;
      addBubble('worker-chat',
        `🤖 *AI Verification:* ${v.verification_status}\n` +
        `Confidence: ${Math.round((v.confidence || 0.7) * 100)}%`
      );
    }
    if (data.customer_reply) {
      showTyping('customer-chat');
      setTimeout(() => {
        removeTyping('customer-chat');
        addBubble('customer-chat', data.customer_reply);
        setStatus('Awaiting customer rating...');
      }, 800);
    }
  } catch (err) {
    removeTyping('worker-chat');
    addBubble('worker-chat', '⚠️ Error uploading completion photo.');
    setStatus('Error');
    console.error(err);
  }
}

/* ---- Voice recording ---- */
let mediaRecorder = null;
let audioChunks = [];
let recordingRole = null;

async function toggleVoice(role) {
  const btnId = `${role}-voice-btn`;
  const btn = document.getElementById(btnId);

  if (mediaRecorder && mediaRecorder.state === 'recording') {
    // Stop recording
    mediaRecorder.stop();
    btn.textContent = '🎤';
    btn.classList.remove('recording');
    return;
  }

  try {
    const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
    mediaRecorder = new MediaRecorder(stream);
    audioChunks = [];
    recordingRole = role;

    mediaRecorder.ondataavailable = e => audioChunks.push(e.data);
    mediaRecorder.onstop = () => sendVoice(role, audioChunks);

    mediaRecorder.start();
    btn.textContent = '⏹';
    btn.classList.add('recording');
    setStatus(`Recording ${role} voice note...`);
  } catch (err) {
    addBubble(`${role}-chat`, '⚠️ Microphone access denied.');
    console.error(err);
  }
}

async function sendVoice(role, chunks) {
  const blob = new Blob(chunks, { type: 'audio/webm' });
  addBubble(`${role}-chat`, '🎤 Voice message sent...', true);
  setStatus('Transcribing voice...');
  showTyping(`${role}-chat`);

  const formData = new FormData();
  formData.append('audio', blob, 'voice.webm');

  try {
    const endpoint = role === 'customer' ? '/api/customer/voice' : '/api/worker/voice';
    const res = await fetch(`${API}${endpoint}`, { method: 'POST', body: formData });
    const data = await res.json();
    removeTyping(`${role}-chat`);

    if (data.transcript) {
      addBubble(`${role}-chat`, `📝 *Transcribed:* ${data.transcript}`);
    }

    const replyKey = `${role}_reply`;
    const otherKey = role === 'customer' ? 'worker_reply' : 'customer_reply';
    const otherChat = role === 'customer' ? 'worker-chat' : 'customer-chat';

    if (data[replyKey]) addBubble(`${role}-chat`, data[replyKey]);
    if (data[otherKey]) {
      showTyping(otherChat);
      setTimeout(() => {
        removeTyping(otherChat);
        addBubble(otherChat, data[otherKey]);
      }, 600);
    }
    setStatus('Ready');
  } catch (err) {
    removeTyping(`${role}-chat`);
    addBubble(`${role}-chat`, '⚠️ Voice processing failed.');
    setStatus('Error');
    console.error(err);
  }
}

/* ---- Reset demo ---- */
async function resetDemo() {
  try {
    await fetch(`${API}/api/reset`, { method: 'POST' });
  } catch (e) { /* ignore */ }

  ['customer-chat', 'worker-chat'].forEach(id => {
    const chat = document.getElementById(id);
    chat.innerHTML = '';
  });

  addBubble('customer-chat',
    '🙏 <strong>Namaste!</strong> Main Karigar AI hoon.<br>' +
    'Aapke ghar ka koi repair kaam hai?<br>' +
    '<em>Type a problem, upload a photo, or record a voice note!</em>'
  );
  addBubble('worker-chat',
    '👋 <strong>Namaste bhai!</strong><br>' +
    'Main Karigar AI hoon — aapko nearby jobs milenge.<br>' +
    '<em>Jobs will appear here automatically!</em>'
  );

  setStatus('Demo reset — ready!');
  ['step-analyze','step-match','step-ping','step-verify'].forEach(s => {
    document.getElementById(s)?.classList.remove('active');
  });
}

/* ---- Enter key in inputs ---- */
document.getElementById('customer-input').addEventListener('keydown', e => {
  if (e.key === 'Enter') sendCustomerMessage();
});
document.getElementById('worker-input').addEventListener('keydown', e => {
  if (e.key === 'Enter') sendWorkerMessage();
});