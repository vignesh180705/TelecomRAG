const form = document.getElementById('chatForm');
const input = document.getElementById('questionInput');
const sendButton = document.getElementById('sendButton');
const sendLabel = document.getElementById('sendLabel');
const messages = document.getElementById('messages');
const welcome = document.getElementById('welcome');
const statusNote = document.getElementById('systemNote');
const statusText = document.getElementById('statusText');
const topK = document.getElementById('topK');
let busy = false;

function escapeHtml(value) {
  return String(value ?? '').replace(/[&<>"']/g, char => ({
    '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;'
  }[char]));
}

// Small markdown renderer suitable for model output. It escapes HTML before formatting.
function renderMarkdown(raw) {
  let text = escapeHtml(raw);
  text = text.replace(/```([\s\S]*?)```/g, (_, code) => `<pre><code>${code.trim()}</code></pre>`);
  text = text.replace(/`([^`]+)`/g, '<code>$1</code>');
  text = text.replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>');
  text = text.replace(/^### (.+)$/gm, '<strong>$1</strong>');
  text = text.replace(/^## (.+)$/gm, '<strong>$1</strong>');
  text = text.replace(/^# (.+)$/gm, '<strong>$1</strong>');
  // Normalize list items into simple HTML lists.
  text = text.replace(/(?:^|\n)((?:[-*] .+(?:\n|$))+)/g, (_, group) => {
    const items = group.trim().split('\n').map(line => `<li>${line.replace(/^[-*] /, '')}</li>`).join('');
    return `\n<ul>${items}</ul>\n`;
  });
  text = text.replace(/(?:^|\n)((?:\d+\. .+(?:\n|$))+)/g, (_, group) => {
    const items = group.trim().split('\n').map(line => `<li>${line.replace(/^\d+\. /, '')}</li>`).join('');
    return `\n<ol>${items}</ol>\n`;
  });
  // Keep already-generated block HTML intact while wrapping other text in paragraphs.
  const blocks = text.split(/(<(?:ul|ol|pre)>[\s\S]*?<\/(?:ul|ol|pre)>)/g).filter(Boolean);
  return blocks.map(part => {
    if (/^<(ul|ol|pre)>/.test(part)) return part;
    return part.trim().split(/\n\s*\n/).filter(Boolean).map(p => `<p>${p.replace(/\n/g, '<br>')}</p>`).join('');
  }).join('');
}

function setStatus(state, message) {
  statusNote.dataset.state = state;
  statusText.textContent = message;
}

async function checkStatus() {
  try {
    const res = await fetch('/api/status');
    const data = await res.json();
    if (data.configured) {
      setStatus('ready', 'Server configuration loaded · Services are checked when you ask a question');
    } else {
      setStatus('error', `Setup required · Missing: ${(data.missing || []).join(', ')}`);
    }
  } catch (_) {
    setStatus('error', 'Backend unavailable · Start the local Flask server to use retrieval');
  }
}

function createMessage(role, text = '') {
  const item = document.createElement('article');
  item.className = `message ${role}`;
  const label = role === 'user' ? 'YOU' : 'ASSISTANT';
  item.innerHTML = `<div class="role-label">${label}</div><div class="message-body"></div>`;
  const body = item.querySelector('.message-body');
  if (role === 'user') {
    const bubble = document.createElement('div');
    bubble.className = 'user-bubble';
    bubble.textContent = text;
    body.appendChild(bubble);
  }
  messages.appendChild(item);
  welcome.hidden = true;
  return { item, body };
}

function formatPage(page) {
  return page === null || page === undefined || page === '' ? 'Page unavailable' : `Page ${page}`;
}

function renderSources(sources) {
  if (!sources || !sources.length) return '';
  const rows = sources.map((source, index) => {
    const doc = escapeHtml(source.document || 'Unknown document');
    const clause = source.clause ? ` · Clause ${escapeHtml(source.clause)}` : '';
    const section = source.section_title ? ` · ${escapeHtml(source.section_title)}` : '';
    const score = Number.isFinite(Number(source.score)) ? Number(source.score).toFixed(4) : 'n/a';
    return `<div class="source-item">
      <div class="source-name">${index + 1}. ${doc}</div>
      <div class="source-meta"><span>${escapeHtml(formatPage(source.page))}</span><span>Similarity ${score}</span><span>Chunk ${escapeHtml(source.chunk_id || 'n/a')}</span>${clause ? `<span>${clause.slice(3)}</span>` : ''}${section ? `<span>${section.slice(3)}</span>` : ''}</div>
      <div class="source-snippet">${escapeHtml(source.snippet || '')}</div>
    </div>`;
  }).join('');
  return `<div class="details-section"><details><summary>Retrieved source chunks <span>${sources.length}</span></summary><div class="details-content">${rows}</div></details></div>`;
}

function renderGraph(edges) {
  if (!edges || !edges.length) return '';
  const rows = edges.slice(0, 40).map(edge => `<div class="graph-row"><span class="graph-node">${escapeHtml(edge.source)}</span> <span class="graph-relation">—[${escapeHtml(edge.relationship)}]→</span> <span class="graph-node">${escapeHtml(edge.target)}</span></div>`).join('');
  const more = edges.length > 40 ? `<p>${edges.length - 40} more relationships were retrieved and are not shown here.</p>` : '';
  return `<div class="details-section"><details><summary>Property-graph context <span>${edges.length}</span></summary><div class="details-content">${rows}${more}</div></details></div>`;
}

function setBusy(value) {
  busy = value;
  sendButton.disabled = value;
  sendLabel.textContent = value ? 'Searching' : 'Ask';
  input.disabled = value;
  topK.disabled = value;
}

async function askQuestion(question) {
  const cleaned = question.trim();
  if (!cleaned || busy) return;
  createMessage('user', cleaned);
  input.value = '';
  resizeInput();

  const assistant = createMessage('assistant');
  assistant.body.innerHTML = '<div class="loading-copy"><span class="loading-line"></span><span>Searching source chunks and connected graph context…</span></div>';
  setBusy(true);
  setStatus('ready', 'Retrieval in progress · Embedding question, searching Neo4j, and generating an answer');
  scrollToBottom();

  try {
    const response = await fetch('/api/chat', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ question: cleaned, top_k: Number(topK.value) })
    });
    const data = await response.json().catch(() => ({}));
    if (!response.ok) throw new Error(data.error || `Request failed with status ${response.status}`);
    assistant.body.innerHTML = `<div class="answer-content">${renderMarkdown(data.answer || 'No answer was returned.')}</div>
      <div class="answer-meta"><span class="meta-chip">${Number(data.retrieved_count || 0)} source chunks</span><span class="meta-chip">${(data.graph_relationships || []).length} graph relationships</span></div>
      ${renderSources(data.sources)}${renderGraph(data.graph_relationships)}`;
    setStatus('ready', 'Answer generated · Source chunks and graph context are available below');
  } catch (error) {
    assistant.body.innerHTML = `<div class="error-box">${escapeHtml(error.message || 'The request failed. Check your server configuration.')}</div>`;
    setStatus('error', 'Request failed · Check the setup instructions and server logs');
  } finally {
    setBusy(false);
    input.focus();
    scrollToBottom();
  }
}

function resizeInput() {
  input.style.height = 'auto';
  input.style.height = `${Math.min(input.scrollHeight, 180)}px`;
}
function scrollToBottom() {
  window.requestAnimationFrame(() => window.scrollTo({ top: document.body.scrollHeight, behavior: 'smooth' }));
}

form.addEventListener('submit', event => {
  event.preventDefault();
  askQuestion(input.value);
});
input.addEventListener('input', resizeInput);
input.addEventListener('keydown', event => {
  if (event.key === 'Enter' && !event.shiftKey) {
    event.preventDefault();
    form.requestSubmit();
  }
});
document.querySelectorAll('[data-prompt]').forEach(button => {
  button.addEventListener('click', () => {
    input.value = button.dataset.prompt;
    resizeInput();
    askQuestion(input.value);
  });
});

checkStatus();
