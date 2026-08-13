/**
 * Form Builder UI Logic
 */

let fbState = {
  schema: {
    schema_id: "default",
    version: 1,
    steps: [
      {
        step_id: "step_1",
        title: "Check Your Land Eligibility",
        description: "Answer a few quick questions and get a preliminary assessment of your land's eligibility for carbon credits.",
        fields: []
      }
    ]
  },
  rules: {
    config_id: "default",
    rules: []
  },
  selectedFieldId: null,
  activeTab: "visual" // 'visual' or 'json'
};

const fbIcons = {
  text: "🔤",
  number: "1️⃣",
  select: "🔽",
  boolean: "✅"
};

const fbLabels = {
  text: "Short Answer",
  number: "Number",
  select: "Dropdown",
  boolean: "Yes / No"
};

function fbInit() {
  fbRenderPalette();
  fbRenderTabs();
  fbRenderCanvas();
}

function generateId() {
  return 'fld_' + Math.random().toString(36).substr(2, 9);
}

function fbRenderPalette() {
  const palette = document.getElementById('fb-palette');
  if (!palette) return;

  const basicFields = [
    { type: 'text', label: 'Short Answer' },
    { type: 'number', label: 'Number' },
    { type: 'select', label: 'Dropdown' },
    { type: 'boolean', label: 'Yes / No' },
  ];

  palette.innerHTML = `
    <div class="fb-palette-category">Basic Fields</div>
    ${basicFields.map(f => `
      <div class="fb-palette-item" onclick="fbAddField('${f.type}')">
        <span class="fb-palette-icon">${fbIcons[f.type]}</span>
        <span>${f.label}</span>
      </div>
    `).join('')}
  `;
}

function fbRenderTabs() {
  const stepper = document.getElementById('fb-stepper');
  if (!stepper) return;

  stepper.innerHTML = `
    <div class="fb-step-wrap ${fbState.activeTab === 'visual' ? 'active' : ''}" onclick="fbSwitchTab('visual')">
      <div class="fb-step-num">1</div>
      <div>Build</div>
    </div>
    <div class="fb-step-divider"></div>
    <div class="fb-step-wrap ${fbState.activeTab === 'json' ? 'active' : ''}" onclick="fbSwitchTab('json')">
      <div class="fb-step-num">2</div>
      <div>Rules JSON</div>
    </div>
  `;
}

function fbSwitchTab(tab) {
  fbState.activeTab = tab;
  fbRenderTabs();
  
  if (tab === 'visual') {
    document.getElementById('fb-visual-view').style.display = 'flex';
    document.getElementById('fb-json-view').style.display = 'none';
  } else {
    document.getElementById('fb-visual-view').style.display = 'none';
    document.getElementById('fb-json-view').style.display = 'block';
    
    // Update JSON textareas from visual state
    document.getElementById('json-form-schema').value = JSON.stringify(fbState.schema, null, 2);
    document.getElementById('json-eval-rules').value = JSON.stringify(fbState.rules, null, 2);
  }
}

function fbGetFieldInputPreview(field) {
  if (field.type === 'text') return `<input type="text" class="fb-input-fake" placeholder="Enter text..." disabled>`;
  if (field.type === 'number') return `<input type="number" class="fb-input-fake" placeholder="Enter number..." disabled>`;
  if (field.type === 'select') {
    const opts = (field.options && field.options.length > 0) ? field.options : ['Option 1'];
    return `
      <select class="fb-input-fake" disabled>
        <option>${opts[0]}</option>
      </select>
    `;
  }
  if (field.type === 'boolean') {
    return `
      <div class="fb-input-fake-row" style="margin-top:8px">
        <label><input type="radio" disabled> Yes</label>
        <label><input type="radio" disabled> No</label>
      </div>
    `;
  }
  return '';
}

function fbRenderCanvas() {
  const canvas = document.getElementById('fb-canvas-content');
  if (!canvas) return;

  const step = fbState.schema.steps[0];

  let html = `
    <div class="fb-canvas-header">
      <h2>🛡️ ${step.title}</h2>
      <p>${step.description}</p>
    </div>
  `;

  step.fields.forEach((field, index) => {
    const isSelected = fbState.selectedFieldId === field.field_id;
    html += `
      <div class="fb-field-card ${isSelected ? 'selected' : ''}" onclick="fbSelectField('${field.field_id}')">
        <div class="fb-field-card-header">
          <div class="fb-drag-handle">↕️</div>
          <div class="fb-field-title">
            ${index + 1}. ${field.label}
            ${field.required ? '<span class="fb-badge-required">Required</span>' : ''}
            <span class="fb-badge-step">Step 1</span>
          </div>
          <div class="fb-field-actions">
            <button title="Duplicate" onclick="event.stopPropagation(); fbDuplicateField('${field.field_id}')">📄</button>
            <button class="delete" title="Delete" onclick="event.stopPropagation(); fbDeleteField('${field.field_id}')">🗑️</button>
          </div>
        </div>
        <div class="fb-field-preview">
          ${field.description ? `<div class="fb-field-description">${field.description}</div>` : ''}
          ${fbGetFieldInputPreview(field)}
        </div>
      </div>
    `;
  });

  html += `
    <div class="fb-add-zone" onclick="fbAddField('text')">
      + Drag a field here or click to add
    </div>
  `;

  canvas.innerHTML = html;
  fbRenderSettings();
}

function fbAddField(type) {
  const newField = {
    field_id: generateId(),
    label: 'New ' + fbLabels[type] + ' Field',
    type: type,
    required: false,
    description: '',
    options: type === 'select' ? ['Option 1', 'Option 2'] : null
  };
  fbState.schema.steps[0].fields.push(newField);
  fbState.selectedFieldId = newField.field_id;
  fbRenderCanvas();
}

function fbDeleteField(id) {
  fbState.schema.steps[0].fields = fbState.schema.steps[0].fields.filter(f => f.field_id !== id);
  if (fbState.selectedFieldId === id) {
    fbState.selectedFieldId = null;
  }
  fbRenderCanvas();
}

function fbDuplicateField(id) {
  const fieldIndex = fbState.schema.steps[0].fields.findIndex(f => f.field_id === id);
  if (fieldIndex > -1) {
    const field = fbState.schema.steps[0].fields[fieldIndex];
    const newField = JSON.parse(JSON.stringify(field));
    newField.field_id = generateId();
    newField.label += ' (Copy)';
    fbState.schema.steps[0].fields.splice(fieldIndex + 1, 0, newField);
    fbState.selectedFieldId = newField.field_id;
    fbRenderCanvas();
  }
}

function fbSelectField(id) {
  fbState.selectedFieldId = id;
  fbRenderCanvas();
}

function fbUpdateSelectedField(key, value) {
  if (!fbState.selectedFieldId) return;
  const field = fbState.schema.steps[0].fields.find(f => f.field_id === fbState.selectedFieldId);
  if (field) {
    field[key] = value;
    fbRenderCanvas();
  }
}

function fbUpdateOptions(index, value) {
  if (!fbState.selectedFieldId) return;
  const field = fbState.schema.steps[0].fields.find(f => f.field_id === fbState.selectedFieldId);
  if (field && field.options) {
    field.options[index] = value;
    fbRenderCanvas();
  }
}

function fbAddOption() {
  if (!fbState.selectedFieldId) return;
  const field = fbState.schema.steps[0].fields.find(f => f.field_id === fbState.selectedFieldId);
  if (field && field.options) {
    field.options.push('New Option');
    fbRenderCanvas();
  }
}

function fbRemoveOption(index) {
  if (!fbState.selectedFieldId) return;
  const field = fbState.schema.steps[0].fields.find(f => f.field_id === fbState.selectedFieldId);
  if (field && field.options) {
    field.options.splice(index, 1);
    fbRenderCanvas();
  }
}

function fbRenderSettings() {
  const sidebar = document.getElementById('fb-settings');
  if (!sidebar) return;

  if (!fbState.selectedFieldId) {
    sidebar.innerHTML = `
      <div class="fb-tabs">
        <div class="fb-tab active">Field Settings</div>
        <div class="fb-tab">Form Settings</div>
      </div>
      <div style="text-align:center; padding: 32px 0; color: #999; font-size:13px;">
        Select a field to edit its settings
      </div>
    `;
    return;
  }

  const field = fbState.schema.steps[0].fields.find(f => f.field_id === fbState.selectedFieldId);
  if (!field) return;

  let optionsHtml = '';
  if (field.type === 'select') {
    optionsHtml = `
      <div class="fb-settings-group">
        <div class="fb-settings-label">Options</div>
        <div class="fb-options-list">
          ${(field.options || []).map((opt, i) => `
            <div class="fb-option-item">
              <input type="text" value="${opt}" onchange="fbUpdateOptions(${i}, this.value)" style="border:none;background:transparent;width:100%;font-size:12px;outline:none;">
              <button style="background:none;border:none;color:#d93025;cursor:pointer" onclick="fbRemoveOption(${i})">✖</button>
            </div>
          `).join('')}
        </div>
        <button class="fb-btn-link" onclick="fbAddOption()">+ Add Option</button>
      </div>
    `;
  }

  sidebar.innerHTML = `
    <div class="fb-tabs">
      <div class="fb-tab active">Field Settings</div>
      <div class="fb-tab">Form Settings</div>
    </div>
    
    <div class="fb-settings-group">
      <div class="fb-settings-label">General</div>
      
      <div class="fb-settings-field">
        <label>Label</label>
        <input type="text" value="${field.label}" onchange="fbUpdateSelectedField('label', this.value)">
      </div>
      
      <div class="fb-settings-field">
        <label>Description</label>
        <textarea rows="2" onchange="fbUpdateSelectedField('description', this.value)">${field.description || ''}</textarea>
      </div>
      
      <div class="fb-settings-field">
        <label>Field Type</label>
        <select onchange="fbUpdateSelectedField('type', this.value)">
          <option value="text" ${field.type === 'text' ? 'selected' : ''}>Short Answer</option>
          <option value="number" ${field.type === 'number' ? 'selected' : ''}>Number</option>
          <option value="select" ${field.type === 'select' ? 'selected' : ''}>Dropdown</option>
          <option value="boolean" ${field.type === 'boolean' ? 'selected' : ''}>Yes / No</option>
        </select>
      </div>
    </div>

    ${optionsHtml}

    <div class="fb-settings-group">
      <div class="fb-toggle-row">
        <span>Required Field</span>
        <label class="fb-toggle">
          <input type="checkbox" ${field.required ? 'checked' : ''} onchange="fbUpdateSelectedField('required', this.checked)">
          <span class="fb-toggle-slider"></span>
        </label>
      </div>
    </div>
  `;
}

// Intercept the original saveFormConfig from index.html
async function fbSaveToServer() {
  try {
    // If we are in JSON view, sync back to visual state first just in case they edited JSON directly
    if (fbState.activeTab === 'json') {
      fbState.schema = JSON.parse(document.getElementById('json-form-schema').value);
      fbState.rules = JSON.parse(document.getElementById('json-eval-rules').value);
    }
    
    let res = await fetch(\`\${API_BASE}/api/admin/form/form-schema\`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json', ...authHeader() },
      body: JSON.stringify(fbState.schema)
    });
    if (!res.ok) throw new Error('Failed to save schema');

    res = await fetch(\`\${API_BASE}/api/admin/form/eval-config\`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json', ...authHeader() },
      body: JSON.stringify(fbState.rules)
    });
    if (!res.ok) throw new Error('Failed to save rules');

    toast('✅ Form & Rules saved successfully', 'ok');
  } catch (e) {
    toast(\`❌ \${e.message}\`, 'err');
  }
}

// Override the original loadFormConfig to populate fbState instead of just textareas
async function loadFormConfig() {
  try {
    const schemaRes = await fetch(\`\${API_BASE}/api/admin/form/form-schema\`, { headers: authHeader() });
    const rulesRes = await fetch(\`\${API_BASE}/api/admin/form/eval-config\`, { headers: authHeader() });
    
    if (schemaRes.ok) fbState.schema = await schemaRes.json();
    if (rulesRes.ok) fbState.rules = await rulesRes.json();
    
    fbInit();
  } catch (e) {
    toast('❌ Failed to load form config', 'err');
  }
}
