/* ============================================================
   COSTOS PRO — Chatbox flotante v2
   Markdown completo: tablas, headings, código, blockquotes, listas
   ============================================================ */

const CostosChatbox = (() => {
  let isOpen    = false;
  let history   = [];
  let agent     = 'general';
  let isLoading = false;

  const AGENTS = [
    { id: 'general',      label: 'General' },
    { id: 'abc',          label: 'ABC' },
    { id: 'proceso',      label: 'Proceso' },
    { id: 'presupuestos', label: 'Presupuesto' },
    { id: 'calidad',      label: 'Calidad' },
    { id: 'manual',       label: 'Manual' },
  ];

  function init() {
    _render();
    _bindEvents();
    setTimeout(() => { if (!isOpen) _showBubble(); }, 3000);
  }

  function _render() {
    const el = document.createElement('div');
    el.id = 'cp-chat-root';
    el.innerHTML = `
      <div id="cp-bubble" class="cp-bubble" style="display:none">
        <strong>Asistente</strong><br>
        ¿Necesitas ayuda con algún módulo o cálculo?
        <button class="cp-bubble-close" onclick="CostosChatbox.hideBubble()">×</button>
      </div>
      <div id="cp-panel" class="chat-panel">
        <div class="chat-header">
          <div class="chat-avatar">CP</div>
          <div class="chat-header-info">
            <div class="chat-header-name">Asistente Costos Pro</div>
            <div class="chat-header-status" id="cp-status">● en línea</div>
          </div>
          <button class="chat-close" onclick="CostosChatbox.close()"><i class="ti ti-x"></i></button>
        </div>
        <div class="chat-agent-tabs" id="cp-tabs">
          ${AGENTS.map(a => `
            <button class="agent-tab ${a.id === agent ? 'active' : ''}"
                    onclick="CostosChatbox.setAgent('${a.id}')"
                    data-agent="${a.id}">${a.label}</button>
          `).join('')}
        </div>
        <div class="chat-messages" id="cp-messages">
          <div class="chat-msg assistant">
            <div class="md-content">Hola 👋 Soy el asistente de <strong>Costos Pro</strong>. Puedo ayudarte con costos ABC, procesos, presupuestos, calidad y más. ¿En qué te ayudo?</div>
          </div>
        </div>
        <div class="chat-input-area">
          <textarea class="chat-input" id="cp-input"
                    placeholder="Escribe tu pregunta..."
                    rows="1"
                    onkeydown="CostosChatbox.handleKey(event)"></textarea>
          <button class="chat-send" id="cp-send" onclick="CostosChatbox.send()">
            <i class="ti ti-send"></i>
          </button>
        </div>
      </div>
      <button class="chat-fab" id="cp-fab" onclick="CostosChatbox.toggle()">
        <i class="ti ti-message-circle"></i>
        <span class="notif-dot" id="cp-notif" style="display:none">1</span>
      </button>
    `;
    document.body.appendChild(el);
    _addStyles();
  }

  function _addStyles() {
    const s = document.createElement('style');
    s.textContent = `
      #cp-chat-root { position:fixed; z-index:9999; }

      /* Burbuja */
      .cp-bubble {
        position:fixed; bottom:88px; right:88px;
        background:white; border:1px solid #E5D5C5;
        border-radius:14px 14px 4px 14px;
        padding:12px 14px; font-size:13px;
        box-shadow:0 4px 16px rgba(0,0,0,0.1);
        max-width:220px; line-height:1.5; color:#1F2937;
      }
      .cp-bubble strong { color:#F97316; }
      .cp-bubble-close {
        position:absolute; top:6px; right:8px;
        background:none; border:none; cursor:pointer;
        font-size:16px; color:#9CA3AF; line-height:1;
      }

      /* ── Markdown renderer ────────────────────────────── */
      .md-content { font-size:13px; line-height:1.65; color:inherit; }

      .md-content h1,.md-content h2,.md-content h3,.md-content h4 {
        font-weight:700; margin:10px 0 5px;
        color: inherit;
      }
      .md-content h1 { font-size:15px; border-bottom:1px solid rgba(255,255,255,0.2); padding-bottom:4px; }
      .md-content h2 { font-size:14px; }
      .md-content h3 { font-size:13.5px; }

      .chat-msg.assistant .md-content h1,
      .chat-msg.assistant .md-content h2,
      .chat-msg.assistant .md-content h3 { color:var(--primary); }

      .md-content p { margin:5px 0; }

      .md-content ul, .md-content ol {
        margin:5px 0 5px 16px; padding:0;
      }
      .md-content li { margin:2px 0; }

      /* Tablas */
      .md-content table {
        border-collapse:collapse; width:100%;
        margin:8px 0; font-size:12px;
      }
      .md-content th {
        background:var(--primary); color:#fff;
        padding:5px 8px; text-align:left;
        font-weight:600; font-size:11px;
      }
      .chat-msg.assistant .md-content th { background:#1F2937; }
      .md-content td {
        padding:4px 8px; border-bottom:1px solid rgba(0,0,0,0.07);
      }
      .md-content tr:nth-child(even) td { background:rgba(0,0,0,0.04); }

      /* Código inline */
      .md-content code {
        background:rgba(0,0,0,0.08);
        padding:1px 5px; border-radius:3px;
        font-family:monospace; font-size:11.5px;
      }
      .chat-msg.user .md-content code {
        background:rgba(255,255,255,0.2);
      }

      /* Bloque de código */
      .md-content pre {
        background:#1F2937; color:#F9FAFB;
        border-radius:6px; padding:10px 12px;
        margin:8px 0; overflow-x:auto;
        font-size:11.5px; line-height:1.5;
      }
      .md-content pre code {
        background:none; padding:0; color:inherit;
        font-size:inherit;
      }

      /* Blockquote */
      .md-content blockquote {
        border-left:3px solid var(--primary);
        margin:6px 0; padding:4px 10px;
        background:rgba(249,115,22,0.08);
        border-radius:0 4px 4px 0;
        font-style:italic;
      }
      .chat-msg.user .md-content blockquote {
        border-left-color:rgba(255,255,255,0.5);
        background:rgba(255,255,255,0.1);
      }

      /* HR */
      .md-content hr {
        border:none; border-top:1px solid rgba(0,0,0,0.1);
        margin:8px 0;
      }

      /* Strong / em */
      .md-content strong { font-weight:700; }
      .md-content em     { font-style:italic; }
    `;
    document.head.appendChild(s);
  }

  function _bindEvents() {
    const input = document.getElementById('cp-input');
    if (input) {
      input.addEventListener('input', () => {
        input.style.height = 'auto';
        input.style.height = Math.min(input.scrollHeight, 100) + 'px';
      });
    }
  }

  /* ── Markdown parser completo ─────────────────────────── */
  function _md(text) {
    if (!text) return '';

    // Escapar HTML primero
    const esc = s => s.replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;');

    let lines = text.split('\n');
    let html  = '';
    let i     = 0;

    while (i < lines.length) {
      const line = lines[i];

      // Bloque de código ```
      if (line.trim().startsWith('```')) {
        const lang = line.trim().slice(3).trim();
        let code = '';
        i++;
        while (i < lines.length && !lines[i].trim().startsWith('```')) {
          code += esc(lines[i]) + '\n';
          i++;
        }
        html += `<pre><code class="lang-${lang}">${code.trimEnd()}</code></pre>`;
        i++;
        continue;
      }

      // Tabla | col1 | col2 |
      if (line.includes('|') && line.trim().startsWith('|')) {
        let tableHtml = '<table>';
        let isHeader  = true;
        while (i < lines.length && lines[i].includes('|') && lines[i].trim().startsWith('|')) {
          const row = lines[i].trim().replace(/^\||\|$/g, '').split('|');
          // Fila separadora |---|---|
          if (row.every(c => /^[-: ]+$/.test(c.trim()))) { isHeader = false; i++; continue; }
          const tag = isHeader ? 'th' : 'td';
          tableHtml += '<tr>' + row.map(c => `<${tag}>${_inline(c.trim())}</${tag}>`).join('') + '</tr>';
          if (isHeader) isHeader = false;
          i++;
        }
        html += tableHtml + '</table>';
        continue;
      }

      // Headings
      const h = line.match(/^(#{1,4})\s+(.+)/);
      if (h) { html += `<h${h[1].length}>${_inline(h[2])}</h${h[1].length}>`; i++; continue; }

      // HR
      if (/^[-*_]{3,}$/.test(line.trim())) { html += '<hr>'; i++; continue; }

      // Blockquote
      if (line.startsWith('>')) {
        let bq = '';
        while (i < lines.length && lines[i].startsWith('>')) {
          bq += _inline(lines[i].slice(1).trim()) + ' ';
          i++;
        }
        html += `<blockquote>${bq.trim()}</blockquote>`;
        continue;
      }

      // Lista desordenada
      if (/^[-*+]\s/.test(line)) {
        html += '<ul>';
        while (i < lines.length && /^[-*+]\s/.test(lines[i])) {
          html += `<li>${_inline(lines[i].slice(2).trim())}</li>`;
          i++;
        }
        html += '</ul>';
        continue;
      }

      // Lista ordenada
      if (/^\d+\.\s/.test(line)) {
        html += '<ol>';
        while (i < lines.length && /^\d+\.\s/.test(lines[i])) {
          html += `<li>${_inline(lines[i].replace(/^\d+\.\s/,'').trim())}</li>`;
          i++;
        }
        html += '</ol>';
        continue;
      }

      // Línea vacía
      if (line.trim() === '') { html += '<br>'; i++; continue; }

      // Párrafo normal
      html += `<p>${_inline(line)}</p>`;
      i++;
    }

    return html;
  }

  function _inline(text) {
    if (!text) return '';
    return text
      // Bold+italic ***text***
      .replace(/\*\*\*(.+?)\*\*\*/g, '<strong><em>$1</em></strong>')
      // Bold **text**
      .replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>')
      // Italic *text*
      .replace(/\*(.+?)\*/g, '<em>$1</em>')
      // Bold __text__
      .replace(/__(.+?)__/g, '<strong>$1</strong>')
      // Italic _text_
      .replace(/_(.+?)_/g, '<em>$1</em>')
      // Inline code `text`
      .replace(/`([^`]+)`/g, '<code>$1</code>')
      // Links [text](url)
      .replace(/\[([^\]]+)\]\(([^)]+)\)/g, '<a href="$2" target="_blank" style="color:var(--primary)">$1</a>');
  }

  /* ── UI helpers ───────────────────────────────────────── */
  function toggle()   { isOpen ? close() : open(); }

  function open() {
    isOpen = true;
    hideBubble();
    document.getElementById('cp-panel').classList.add('open');
    document.getElementById('cp-notif').style.display = 'none';
    document.getElementById('cp-fab').querySelector('i').className = 'ti ti-x';
    setTimeout(() => document.getElementById('cp-input').focus(), 100);
  }

  function close() {
    isOpen = false;
    document.getElementById('cp-panel').classList.remove('open');
    document.getElementById('cp-fab').querySelector('i').className = 'ti ti-message-circle';
  }

  function _showBubble() {
    const b = document.getElementById('cp-bubble');
    if (b && !isOpen) {
      b.style.display = 'block';
      document.getElementById('cp-notif').style.display = 'flex';
    }
  }

  function hideBubble() {
    const b = document.getElementById('cp-bubble');
    if (b) b.style.display = 'none';
  }

  function setAgent(agentId) {
    agent   = agentId;
    history = [];
    document.querySelectorAll('.agent-tab').forEach(tab => {
      tab.classList.toggle('active', tab.dataset.agent === agentId);
    });
    _appendMsg('assistant', `Cambiaste al agente **${agentId}**. ¿En qué te ayudo?`);
  }

  function handleKey(e) {
    if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); send(); }
  }

  function _appendMsg(role, text) {
    const msgs = document.getElementById('cp-messages');
    const div  = document.createElement('div');
    div.className = `chat-msg ${role}`;
    div.innerHTML = `<div class="md-content">${_md(text)}</div>`;
    msgs.appendChild(div);
    msgs.scrollTop = msgs.scrollHeight;
    return div;
  }

  function _appendTyping() {
    const msgs = document.getElementById('cp-messages');
    const div  = document.createElement('div');
    div.id = 'cp-typing';
    div.className = 'chat-msg assistant';
    div.innerHTML = '<div class="md-content" style="opacity:0.6"><em>escribiendo...</em></div>';
    msgs.appendChild(div);
    msgs.scrollTop = msgs.scrollHeight;
  }

  function _removeTyping() {
    document.getElementById('cp-typing')?.remove();
  }

  function _setLoading(v) {
    isLoading = v;
    const btn = document.getElementById('cp-send');
    if (btn) btn.disabled = v;
    document.getElementById('cp-status').textContent = v ? '⏳ procesando...' : '● en línea';
  }

  async function send() {
    const input = document.getElementById('cp-input');
    const text  = input.value.trim();
    if (!text || isLoading) return;

    input.value = '';
    input.style.height = 'auto';
    _appendMsg('user', text);
    history.push({ role: 'user', content: text });

    _setLoading(true);
    _appendTyping();

    try {
      const res  = await fetch('/ai/chat', {
        method:  'POST',
        headers: { 'Content-Type': 'application/json' },
        body:    JSON.stringify({ message: text, history, agent })
      });
      const data = await res.json();
      _removeTyping();

      if (data.success) {
        _appendMsg('assistant', data.response);
        history.push({ role: 'assistant', content: data.response });
        if (history.length > 20) history = history.slice(-20);
        if (window.CostosProVoice?.isEnabled()) {
          // Solo leer el texto plano, sin markdown
          const plain = data.response.replace(/[#*`|>_~\[\]]/g,'').substring(0,200);
          window.CostosProVoice.speak(plain);
        }
      } else {
        _appendMsg('assistant', `⚠️ ${data.error || 'Error al conectar con la IA'}`);
      }
    } catch (err) {
      _removeTyping();
      _appendMsg('assistant', '⚠️ Error de conexión. Verifica tu ANTHROPIC_API_KEY en `.env`');
    }

    _setLoading(false);
  }

  function sendQuick(text, agentId = null) {
    if (agentId) setAgent(agentId);
    if (!isOpen) open();
    const input = document.getElementById('cp-input');
    if (input) { input.value = text; send(); }
  }

  document.addEventListener('DOMContentLoaded', init);

  return { toggle, open, close, hideBubble, send, sendQuick, setAgent, handleKey, renderMd: _md };
})();

window.CostosChatbox = CostosChatbox;

// Exportar renderizador de markdown globalmente para otros componentes
window.renderMarkdown = function(text) {
  return CostosChatbox.renderMd(text);
};
