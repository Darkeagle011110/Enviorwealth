
// ── Config ──────────────────────────────────────────────────────────────────
// Globals are already declared in index.html

function onMultilingualToggle() {
  const isEnabled = document.getElementById('toggle-multilingual').checked;
  const settingsDiv = document.getElementById('multilingual-settings');
  settingsDiv.style.display = isEnabled ? 'block' : 'none';
  
  if (isEnabled) {
    // Show 5s popup warning
    const popup = document.createElement('div');
    popup.style.cssText = `position:fixed; top:24px; left:50%; transform:translateX(-50%); background:var(--warn); color:#000; padding:16px 24px; border-radius:var(--radius-sm); z-index:10000; font-weight:600; font-size:14px; box-shadow:var(--shadow); animation:slideDown 0.3s ease;`;
    popup.innerHTML = `⚠️ Ensure you switch the LLM and TTS/STT models to a robust multilingual model (like GPT-4o or Claude 3.5) for optimal performance.`;
    document.body.appendChild(popup);
    setTimeout(() => {
      popup.style.animation = 'slideUp 0.3s ease forwards';
      setTimeout(() => popup.remove(), 300);
    }, 5000);
  }
}

async function saveMultilingualConfig() {
  const isEnabled = document.getElementById('toggle-multilingual').checked;
  const audioProvider = document.getElementById('multi-audio-provider').value;
  try {
    const res = await fetch(`${API_BASE}/api/admin/channels/multilingual`, {
      method: 'POST', headers: headers(),
      body: JSON.stringify({ enabled: isEnabled, audio_provider: audioProvider, supported_languages: ["hi", "gu", "mr"] })
    });
    const data = await res.json();
    toast(`✅ ${data.message}`, 'ok');
  } catch (e) { toast(`❌ Error: ${e.message}`, 'err'); }
}

async function doLogin() {
  const user = document.getElementById('inp-username').value;
  const pass = document.getElementById('inp-password').value;
  const btn = document.querySelector('#login-modal .btn-primary');
  btn.textContent = 'Logging in...';
  
  const formData = new URLSearchParams();
  formData.append('username', user);
  formData.append('password', pass);
  
  try {
    const res = await fetch(`${API_BASE}/api/admin/login`, {
      method: 'POST',
      body: formData
    });
    if (res.ok) {
      const data = await res.json();
      localStorage.setItem('admin_token', data.access_token);
      ADMIN_TOKEN = data.access_token;
      document.getElementById('login-modal').classList.remove('open');
      btn.textContent = 'Login';
      navigate('llm');
    } else {
      alert('Login failed. Please check credentials.');
      btn.textContent = 'Login';
    }
  } catch(e) {
    alert('Login error: ' + e.message);
    btn.textContent = 'Login';
  }
}

function logout() {
  localStorage.removeItem('admin_token');
  ADMIN_TOKEN = '';
  document.getElementById('login-modal').classList.add('open');
}

// ── Provider → Models mapping ────────────────────────────────────────────────
const PROVIDER_MODELS = {
  claude:  ['claude-3-5-sonnet-20241022','claude-3-5-haiku-20241022','claude-3-opus-20240229','claude-3-haiku-20240307'],
  openai:  ['gpt-4o','gpt-4o-mini','gpt-3.5-turbo'],
  groq:    ['llama-3.3-70b-versatile','llama-3.1-8b-instant','openai/gpt-oss-120b','openai/gpt-oss-20b'],
  gemini:  ['gemini-2.0-flash-exp','gemini-1.5-pro','gemini-1.5-flash','gemini-1.5-flash-8b'],
};

const PROVIDER_ICONS = { claude:'🧠', openai:'⚡', groq:'🚀', gemini:'💫' };
const PROVIDER_LABELS = { claude:'Claude (Anthropic)', openai:'OpenAI GPT', groq:'Groq (Llama/Mixtral)', gemini:'Google Gemini' };

// ── Navigation ───────────────────────────────────────────────────────────────
function navigate(page) {
  document.querySelectorAll('.page').forEach(p => p.classList.remove('active'));
  document.querySelectorAll('.nav-item').forEach(n => n.classList.remove('active'));
  document.getElementById('page-' + page).classList.add('active');

  const navMap = { 
    dashboard: 0, 
    llm: 1, 
    docs: 2, 
    geo: 3, 
    channels: 4, 
    health: 5 
  };
  if (navMap[page] !== undefined) {
    document.querySelectorAll('.nav-item')[navMap[page]].classList.add('active');
  }

  if (page === 'docs') loadDocs();
  if (page === 'health') loadHealth();
  if (page === 'llm') refreshStatus();
  if (page === 'geo') loadGeoStatus();
}

// ── Provider change ──────────────────────────────────────────────────────────
function onProviderChange() {
  const provider = document.getElementById('sel-provider').value;
  const modelSel = document.getElementById('sel-model');
  modelSel.innerHTML = '';
  if (!provider) { modelSel.innerHTML = '<option>Select provider first...</option>'; return; }
  (PROVIDER_MODELS[provider] || []).forEach(m => {
    const opt = document.createElement('option');
    opt.value = m; opt.textContent = m;
    modelSel.appendChild(opt);
  });
  document.getElementById('active-avatar').textContent = PROVIDER_ICONS[provider] || '🤖';
}

// ── Tab switch ───────────────────────────────────────────────────────────────
function switchTab(tab, el) {
  document.querySelectorAll('.tab').forEach(t => t.classList.remove('active'));
  el.classList.add('active');
  document.getElementById('current-tab-is-fallback').value = (tab === 'fallback') ? 'true' : 'false';
}

// ── Toggle API key visibility ────────────────────────────────────────────────
function toggleKey() {
  const inp = document.getElementById('inp-apikey');
  inp.type = inp.type === 'password' ? 'text' : 'password';
}

// ── Test Only (no switch) ────────────────────────────────────────────────────
async function testOnly() {
  const { provider, model, apiKey } = getFormValues();
  if (!validate(provider, model, apiKey)) return;
  showHealth('loading', '🔄 Testing connection...');
  try {
    const res = await fetch(`${API_BASE}/api/admin/llm/test`, {
      method: 'POST', headers: { 'Content-Type': 'application/json', ...headers() },
      body: JSON.stringify({ provider, model_name: model, api_key: apiKey }),
    });
    const data = await res.json();
    if (data.status === 'ok') {
      showHealth('ok', `✅ Connected — ${data.latency_ms}ms — ${data.model_used}`);
    } else {
      showHealth('error', `❌ ${data.error}`);
    }
  } catch(e) { showHealth('error', `❌ Request failed: ${e.message}`); }
}

// ── Save & Switch ────────────────────────────────────────────────────────────
async function saveAndSwitch() {
  const { provider, model, apiKey } = getFormValues();
  if (!validate(provider, model, apiKey)) return;
  const isFallback = document.getElementById('current-tab-is-fallback').value === 'true';
  const btn = document.getElementById('btn-save');
  btn.disabled = true;
  btn.innerHTML = '<div class="spinner"></div> Testing & Switching...';
  showHealth('loading', '🔄 Running health check before switching...');
  try {
    const res = await fetch(`${API_BASE}/api/admin/llm/switch`, {
      method: 'POST', headers: { 'Content-Type': 'application/json', ...headers() },
      body: JSON.stringify({ provider, model_name: model, api_key: apiKey, is_fallback: isFallback }),
    });
    const data = await res.json();
    if (data.switched) {
      showHealth('ok', `✅ Switched! ${data.health_check.latency_ms}ms · ${data.message}`);
      toast(data.message, 'ok');
      refreshStatus();
    } else {
      showHealth('error', `❌ ${data.message}`);
      toast('Switch failed — previous config preserved', 'err');
    }
  } catch(e) {
    showHealth('error', `❌ Request failed: ${e.message}`);
  } finally {
    btn.disabled = false;
    btn.innerHTML = '<span>⚡</span> Save &amp; Switch';
  }
}

// ── Refresh status banner ────────────────────────────────────────────────────
async function refreshStatus() {
  try {
    const res = await fetch(`${API_BASE}/api/admin/llm/status`, { headers: headers() });
    const data = await res.json();
    const primary = data.primary;
    const fallback = data.fallback;
    if (primary) {
      document.getElementById('active-model-name').textContent =
        `${PROVIDER_LABELS[primary.provider] || primary.provider} — ${primary.model_name}`;
      document.getElementById('active-avatar').textContent = PROVIDER_ICONS[primary.provider] || '🤖';
    } else {
      document.getElementById('active-model-name').textContent = 'No model configured';
    }
    const statusDiv = document.getElementById('llm-status-display');
    statusDiv.innerHTML = `
      <div style="margin-bottom:14px">
        <div style="font-size:11px;color:var(--text-muted);margin-bottom:8px;text-transform:uppercase;letter-spacing:.06em">Primary</div>
        ${primary ? `
          <div style="display:flex;align-items:center;gap:10px;padding:12px;background:rgba(16,185,129,0.08);border:1px solid rgba(16,185,129,0.2);border-radius:8px">
            <span style="font-size:22px">${PROVIDER_ICONS[primary.provider]||'🤖'}</span>
            <div>
              <div style="font-size:13px;font-weight:600">${primary.model_name}</div>
              <div style="font-size:11px;color:var(--text-muted)">${PROVIDER_LABELS[primary.provider]||primary.provider}</div>
            </div>
            <span class="badge badge-success" style="margin-left:auto">● Active</span>
          </div>` : `<div style="color:var(--text-muted);font-size:13px">Not configured</div>`}
      </div>
      <div>
        <div style="font-size:11px;color:var(--text-muted);margin-bottom:8px;text-transform:uppercase;letter-spacing:.06em">Fallback</div>
        ${fallback ? `
          <div style="display:flex;align-items:center;gap:10px;padding:12px;background:rgba(245,158,11,0.08);border:1px solid rgba(245,158,11,0.2);border-radius:8px">
            <span style="font-size:22px">${PROVIDER_ICONS[fallback.provider]||'🛡️'}</span>
            <div>
              <div style="font-size:13px;font-weight:600">${fallback.model_name}</div>
              <div style="font-size:11px;color:var(--text-muted)">${PROVIDER_LABELS[fallback.provider]||fallback.provider}</div>
            </div>
            <span class="badge badge-warn" style="margin-left:auto">Standby</span>
          </div>` : `<div style="color:var(--text-muted);font-size:13px;padding:12px;border:1px dashed var(--border);border-radius:8px;text-align:center">
            No fallback configured — click Fallback tab to add one
          </div>`}
      </div>`;
  } catch(e) {
    console.error('Status fetch failed:', e);
  }
}

// ── Document Corpus ──────────────────────────────────────────────────────────
async function loadDocs() {
  const tbody = document.getElementById('docs-table-body');
  tbody.innerHTML = '<tr><td colspan="7" style="text-align:center;color:var(--text-muted);padding:32px">Loading...</td></tr>';
  try {
    const res = await fetch(`${API_BASE}/api/admin/documents`, { headers: headers() });
    const data = await res.json();
    if (!data.documents || data.documents.length === 0) {
      tbody.innerHTML = '<tr><td colspan="7" style="text-align:center;color:var(--text-muted);padding:40px">No documents in corpus yet. Upload your first document.</td></tr>';
      return;
    }
    tbody.innerHTML = data.documents.map(d => `
      <tr>
        <td><div style="font-weight:500">${d.title}</div><div style="font-size:11px;color:var(--text-muted)">${d.standard_body||''} · ${d.doc_type||''}</div></td>
        <td><span class="badge badge-muted">${d.version||'—'}</span></td>
        <td class="td-mono">${d.effective_date||'—'}</td>
        <td><span class="badge badge-muted">${d.jurisdiction||'global'}</span></td>
        <td><span style="color:var(--accent);font-weight:600">${d.chunk_count}</span></td>
        <td class="td-mono" style="font-size:11px">${d.retrieval_date}</td>
        <td>
          <div style="display:flex;gap:6px">
            <button class="btn btn-secondary btn-sm" onclick="openReplaceModal('${d.id}','${d.title}')">🔄 Replace</button>
            <button class="btn btn-danger btn-sm" onclick="deleteDoc('${d.id}','${d.title}')">🗑️</button>
          </div>
        </td>
      </tr>`).join('');
  } catch(e) {
    tbody.innerHTML = `<tr><td colspan="7" style="text-align:center;color:var(--error);padding:32px">Error loading documents: ${e.message}</td></tr>`;
  }
}

let sourcesLoaded = false;
async function toggleSources() {
  const el = document.getElementById('recommended-sources');
  const chevron = document.getElementById('sources-chevron');
  const isVisible = el.style.display === 'block';
  el.style.display = isVisible ? 'none' : 'block';
  chevron.style.transform = isVisible ? 'rotate(0deg)' : 'rotate(180deg)';
  
  if (!isVisible && !sourcesLoaded) {
    const tbody = document.getElementById('sources-table-body');
    try {
      const res = await fetch(`${API_BASE}/api/admin/corpus/recommended-sources`, { headers: headers() });
      const data = await res.json();
      tbody.innerHTML = data.sources.map(s => `
        <tr>
          <td style="font-weight:500">${s.name}</td>
          <td style="font-size:12px; color:var(--text-secondary)">${s.description}</td>
          <td><a href="${s.url}" target="_blank" style="color:var(--accent); text-decoration:none; font-size:12px; display:flex; align-items:center; gap:4px;">⬇️ Download <span style="font-size:10px">↗</span></a></td>
        </tr>
      `).join('');
      sourcesLoaded = true;
    } catch(e) {
      tbody.innerHTML = `<tr><td colspan="3" style="text-align:center;color:var(--error);padding:16px">Error: ${e.message}</td></tr>`;
    }
  }
}

function openUploadModal() { document.getElementById('upload-modal').classList.add('open'); }
function closeUploadModal() { document.getElementById('upload-modal').classList.remove('open'); resetUploadForm(); }

function onFileSelect(e) {
  const file = e.target.files[0];
  if (file) document.getElementById('drop-text').textContent = `Selected: ${file.name}`;
}

// Drag & drop
const dropZone = document.getElementById('drop-zone');
dropZone.addEventListener('dragover', e => { e.preventDefault(); dropZone.classList.add('drag-over'); });
dropZone.addEventListener('dragleave', () => dropZone.classList.remove('drag-over'));
dropZone.addEventListener('drop', e => {
  e.preventDefault(); dropZone.classList.remove('drag-over');
  const file = e.dataTransfer.files[0];
  if (file) { document.getElementById('file-input').files = e.dataTransfer.files; document.getElementById('drop-text').textContent = `Selected: ${file.name}`; }
});

async function doUpload() {
  const file = document.getElementById('file-input').files[0];
  const title = document.getElementById('doc-title').value.trim();
  if (!file || !title) { toast('Please select a file and enter a title', 'err'); return; }

  const fd = new FormData();
  fd.append('file', file);
  fd.append('title', title);
  fd.append('version', document.getElementById('doc-version').value);
  fd.append('effective_date', document.getElementById('doc-eff-date').value);
  fd.append('jurisdiction', document.getElementById('doc-jurisdiction').value);
  fd.append('doc_type', document.getElementById('doc-type').value);

  document.getElementById('btn-upload').disabled = true;
  document.getElementById('upload-progress').style.display = 'block';
  document.getElementById('progress-fill').style.width = '30%';
  document.getElementById('progress-text').textContent = 'Uploading & indexing...';

  try {
    const res = await fetch(`${API_BASE}/api/admin/documents/upload`, {
      method: 'POST',
      headers: authHeader(),
      body: fd,
    });
    document.getElementById('progress-fill').style.width = '100%';
    const data = await res.json();
    document.getElementById('progress-text').textContent = data.message;
    toast(`✅ ${data.message}`, 'ok');
    setTimeout(() => { closeUploadModal(); loadDocs(); }, 1200);
  } catch(e) {
    toast(`❌ Upload failed: ${e.message}`, 'err');
    document.getElementById('progress-text').textContent = 'Upload failed.';
  } finally {
    document.getElementById('btn-upload').disabled = false;
  }
}

function resetUploadForm() {
  document.getElementById('file-input').value = '';
  document.getElementById('drop-text').textContent = 'Click to select or drag & drop';
  document.getElementById('doc-title').value = '';
  document.getElementById('doc-version').value = '';
  document.getElementById('doc-eff-date').value = '';
  document.getElementById('upload-progress').style.display = 'none';
  document.getElementById('progress-fill').style.width = '0%';
}

async function deleteDoc(id, title) {
  if (!confirm(`Archive document "${title}"?\nIt will be removed from active retrieval (not permanently deleted).`)) return;
  try {
    await fetch(`${API_BASE}/api/admin/documents/${id}`, { method: 'DELETE', headers: headers() });
    toast(`✅ "${title}" archived`, 'ok');
    loadDocs();
  } catch(e) { toast(`❌ ${e.message}`, 'err'); }
}

function openReplaceModal(id, title) {
  // For simplicity, reuse the upload modal with replace mode
  openUploadModal();
  document.getElementById('doc-title').value = title;
  document.getElementById('btn-upload').textContent = '🔄 Replace & Re-index';
  document.getElementById('btn-upload').onclick = () => doReplace(id);
}

async function doReplace(docId) {
  const file = document.getElementById('file-input').files[0];
  if (!file) { toast('Please select a replacement file', 'err'); return; }
  const fd = new FormData();
  fd.append('file', file);
  fd.append('version', document.getElementById('doc-version').value);
  fd.append('effective_date', document.getElementById('doc-eff-date').value);
  try {
    const res = await fetch(`${API_BASE}/api/admin/documents/${docId}/replace`, {
      method: 'PUT', headers: authHeader(), body: fd,
    });
    const data = await res.json();
    toast(`✅ ${data.message}`, 'ok');
    closeUploadModal();
    loadDocs();
  } catch(e) { toast(`❌ ${e.message}`, 'err'); }
}

// ── System Health ─────────────────────────────────────────────────────────────
async function loadHealth() {
  try {
    const res = await fetch(`${API_BASE}/health`);
    const data = await res.json();
    const llm = data.llm;
    document.getElementById('health-llm').textContent =
      llm.primary_ready ? `✅ ${llm.primary?.model_name || 'Ready'}` : '⚠️ Not configured';
  } catch(e) {
    document.getElementById('health-llm').textContent = '❌ API unreachable';
  }
}

// ── Helpers ──────────────────────────────────────────────────────────────────
function getFormValues() {
  return {
    provider: document.getElementById('sel-provider').value,
    model: document.getElementById('sel-model').value,
    apiKey: document.getElementById('inp-apikey').value.trim(),
  };
}

function validate(provider, model, apiKey) {
  if (!provider) { toast('Please select a provider', 'err'); return false; }
  if (!model) { toast('Please select a model', 'err'); return false; }
  if (!apiKey) { toast('Please enter an API key', 'err'); return false; }
  return true;
}

function showHealth(type, msg) {
  const el = document.getElementById('health-result');
  el.className = 'health-result ' + type;
  el.style.display = 'flex';
  el.innerHTML = type === 'loading'
    ? `<div class="spinner"></div><span>${msg}</span>`
    : `<span>${msg}</span>`;
}

function toast(msg, type = 'ok') {
  const el = document.getElementById('toast');
  el.className = `toast-${type}`;
  el.style.display = 'flex';
  el.textContent = msg;
  setTimeout(() => { el.style.display = 'none'; }, 4000);
}

function initAdmin() {
  refreshStatus();
  if (document.getElementById('page-docs').classList.contains('active')) {
    loadDocs();
  } else if (document.getElementById('page-dashboard').classList.contains('active')) {
    loadDashboard();
    fetchLeads();
  }
}

if (!ADMIN_TOKEN) {
  document.getElementById('login-modal').classList.add('open');
} else {
  initAdmin();
}

    async function saveGeeKey() {
      const keyStr = document.getElementById('inp-gee-key').value.trim();
      if (!keyStr) return showToast('Please enter the service account JSON', 'err');
      
      try {
        const res = await fetch(`${API_BASE}/api/admin/geospatial/gee-key`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json', ...headers() },
          body: JSON.stringify({ service_account_json: keyStr })
        });
        const data = await res.json();
        if(res.ok) {
          showToast('GEE Key saved successfully!', 'ok');
          document.getElementById('inp-gee-key').value = '';
        } else {
          showToast('Error: ' + (data.detail || 'Failed to save'), 'err');
        }
      } catch (err) {
        showToast('Network error', 'err');
      }
    }

    async function uploadOneData(file) {
      if (!file) return;
      const formData = new FormData();
      formData.append('file', file);
      
      try {
        showToast('Uploading...', 'ok');
        const res = await fetch(`${API_BASE}/api/admin/geospatial/one-data`, {
          method: 'POST',
          headers: headers(),
          body: formData
        });
        const data = await res.json();
        if(res.ok) {
          showToast('ONE Data uploaded successfully!', 'ok');
        } else {
          showToast('Error: ' + (data.detail || 'Failed to upload'), 'err');
        }
      } catch (err) {
        showToast('Network error', 'err');
      }
      document.getElementById('one-file-input').value = '';
    }

    async function loadGeoStatus() {
      try {
        const res = await fetch(`${API_BASE}/api/admin/geospatial/status`, { headers: headers() });
        const data = await res.json();
        const banner = document.getElementById('geo-validation-banner');
        const icon = document.getElementById('geo-banner-icon');
        const title = document.getElementById('geo-banner-title');
        const text = document.getElementById('geo-banner-text');

        banner.style.display = 'flex';
        if (data.features_active) {
          banner.style.background = 'rgba(16,185,129,0.1)';
          banner.style.borderColor = 'rgba(16,185,129,0.3)';
          banner.style.color = 'var(--success)';
          icon.textContent = '✅';
          title.textContent = 'Geospatial Features Active';
          text.textContent = 'GEE and ONE data are configured correctly. Full analysis is enabled.';
        } else {
          banner.style.background = 'rgba(239,68,68,0.1)';
          banner.style.borderColor = 'rgba(239,68,68,0.3)';
          banner.style.color = 'var(--error)';
          icon.textContent = '⚠️';
          title.textContent = 'Action Required: Geospatial Incomplete';
          let missing = [];
          if (!data.gee_valid) missing.push('valid GEE Service Account');
          if (!data.one_data_loaded) missing.push('ONE GeoJSON dataset');
          text.textContent = 'Missing: ' + missing.join(' and ') + '. Tree cover stats and ONE checks will be skipped until configured.';
        }
      } catch (e) {
        console.error('Failed to load geo status', e);
      }
    }

    // ── Channels & Localization ──────────────────────────────────────────────
    function onAudioProviderChange() {
      const provider = document.getElementById('sel-audio-provider').value;
      if (provider === 'bhashini') {
        document.getElementById('audio-config-bhashini').style.display = 'block';
        document.getElementById('audio-config-generic').style.display = 'none';
      } else {
        document.getElementById('audio-config-bhashini').style.display = 'none';
        document.getElementById('audio-config-generic').style.display = 'block';
      }
    }

    async function saveWhatsAppConfig() {
      const phoneId = document.getElementById('inp-wa-phone-id').value.trim();
      const token = document.getElementById('inp-wa-token').value.trim();
      const verifyToken = document.getElementById('inp-wa-verify').value.trim();

      if (!phoneId || !token || !verifyToken) {
        return toast('Please fill in all WhatsApp fields', 'err');
      }

      try {
        const res = await fetch(`${API_BASE}/api/admin/channels/whatsapp`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json', ...headers() },
          body: JSON.stringify({ phone_number_id: phoneId, access_token: token, verify_token: verifyToken })
        });
        if (res.ok) toast('✅ WhatsApp Config saved!', 'ok');
        else toast('❌ Failed to save config', 'err');
      } catch (e) {
        toast('❌ Network error', 'err');
      }
    }

    async function saveAudioConfig() {
      const provider = document.getElementById('sel-audio-provider').value;
      let payload = { provider };

      if (provider === 'bhashini') {
        payload.user_id = document.getElementById('inp-bh-userid').value.trim();
        payload.api_key = document.getElementById('inp-bh-apikey').value.trim();
        payload.pipeline_id = document.getElementById('inp-bh-pipeline').value.trim();
        if (!payload.user_id || !payload.api_key || !payload.pipeline_id) {
          return toast('Please fill all Bhashini fields', 'err');
        }
      } else {
        payload.api_key = document.getElementById('inp-generic-audio-key').value.trim();
        if (!payload.api_key) return toast('Please enter the API key', 'err');
      }

      try {
        const res = await fetch(`${API_BASE}/api/admin/channels/audio`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json', ...headers() },
          body: JSON.stringify(payload)
        });
        if (res.ok) toast('✅ Audio Config saved!', 'ok');
        else toast('❌ Failed to save config', 'err');
      } catch (e) {
        toast('❌ Network error', 'err');
      }
    }

    // ── Dashboard & Leads ────────────────────────────────────────────────────
    async function loadDashboard() {
      try {
        const res = await fetch(`${API_BASE}/api/admin/dashboard/kpis`, { headers: headers() });
        const data = await res.json();
        document.getElementById('kpi-users').textContent = data.total_users;
        document.getElementById('kpi-started').textContent = data.assessments_started;
        document.getElementById('kpi-completed').textContent = data.assessments_completed;
        document.getElementById('kpi-promising').textContent = data.eligible_promising;
        document.getElementById('kpi-aggregation').textContent = data.aggregation_candidates;
        document.getElementById('kpi-leads').textContent = data.leads_generated;
        document.getElementById('kpi-conversion').textContent = data.lead_conversion + '%';
        document.getElementById('kpi-time').textContent = data.average_assessment_completion;
      } catch (e) {
        console.error('Failed to load KPIs:', e);
      }
    }

    async function fetchLeads() {
      const tbody = document.querySelector('#leads-table tbody');
      tbody.innerHTML = '<tr><td colspan="7" style="text-align: center; color: var(--text-muted)">Loading leads...</td></tr>';
      try {
        const res = await fetch(`${API_BASE}/api/admin/leads`, { headers: headers() });
        const data = await res.json();
        if (data.length === 0) {
            tbody.innerHTML = '<tr><td colspan="7" style="text-align: center; color: var(--text-muted)">No leads found.</td></tr>';
            return;
        }
        tbody.innerHTML = data.map(L => `
          <tr style="cursor: pointer" onclick="openLeadModal('${L.id}')">
            <td>
              <div style="font-weight: 500">${L.name}</div>
              <div style="font-size: 11px; color: var(--text-muted)">ID: ${L.id.substring(0,8)}</div>
            </td>
            <td>${L.location}</td>
            <td class="td-mono">${L.area} ha</td>
            <td>
              <span class="badge ${L.verdict.toLowerCase().includes('promising') ? 'badge-success' : L.verdict.toLowerCase().includes('aggregation') ? 'badge-warn' : 'badge-muted'}">
                ${L.verdict.substring(0,25)}
              </span>
            </td>
            <td><span class="badge badge-muted">${L.intent}</span></td>
            <td>
              <span class="badge ${L.status === 'new' ? 'badge-success' : L.status === 'disqualified' ? 'badge-error' : 'badge-warn'}">
                ${L.status}
              </span>
            </td>
            <td>
              <button class="btn btn-secondary btn-sm" onclick="event.stopPropagation(); openLeadModal('${L.id}')">View</button>
            </td>
          </tr>
        `).join('');
      } catch (e) {
        tbody.innerHTML = '<tr><td colspan="7" style="text-align: center; color: var(--error)">Failed to load leads</td></tr>';
      }
    }

    let currentLeadId = null;

    async function openLeadModal(id) {
      currentLeadId = id;
      document.getElementById('lead-modal').style.display = 'block';
      document.getElementById('modal-lead-name').textContent = 'Loading...';
      
      try {
        const res = await fetch(`${API_BASE}/api/admin/leads/${id}`, { headers: headers() });
        const data = await res.json();
        
        document.getElementById('modal-lead-name').textContent = data.personal_info?.name || 'Anonymous Lead';
        document.getElementById('modal-status').value = data.status || 'new';
        
        const pi = data.personal_info || {};
        document.getElementById('modal-personal-info').innerHTML = `
          <div><strong>Mobile:</strong> ${pi.mobile || '-'}</div>
          <div><strong>Email:</strong> ${pi.email || '-'}</div>
          <div><strong>State:</strong> ${data.land_info?.state || '-'}</div>
          <div><strong>Lead Score:</strong> <span class="badge ${data.lead_score === 'Hot' ? 'badge-success' : 'badge-muted'}">${data.lead_score || 'None'}</span></div>
        `;
        
        const li = data.land_info || {};
        document.getElementById('modal-land-info').innerHTML = `
          <div><strong>Area:</strong> ${li.area_ha || 0} ha</div>
          <div><strong>Tenure:</strong> ${li.tenure_type || '-'}</div>
          <div><strong>Legal Class:</strong> ${li.land_legal_class || '-'}</div>
          <hr style="border: 0; border-top: 1px solid var(--border); margin: 8px 0" />
          <div><strong>Verdict:</strong> ${data.verdict || '-'}</div>
          <div><strong>Confidence:</strong> ${data.confidence || '-'}</div>
        `;
        
        const conv = data.conversation || [];
        document.getElementById('modal-conversation').innerHTML = conv.map(m => `
          <div style="margin-bottom: 8px;">
            <strong style="color: ${m.role === 'user' ? 'var(--accent)' : 'var(--text-secondary)'}">${m.role === 'user' ? 'User' : 'Assistant'}:</strong>
            <span style="white-space: pre-wrap">${m.content}</span>
          </div>
        `).join('');
      } catch (e) {
        console.error('Failed to load lead details', e);
      }
    }

    async function updateLeadStatus() {
      if (!currentLeadId) return;
      const status = document.getElementById('modal-status').value;
      
      try {
        await fetch(`${API_BASE}/api/admin/leads/${currentLeadId}/status`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json', ...headers() },
          body: JSON.stringify({ status })
        });
        toast('Lead status updated', 'ok');
        fetchLeads();
      } catch (e) {
        toast('Failed to update status', 'err');
      }
    }
  