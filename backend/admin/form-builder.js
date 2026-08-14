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
        fields: [
          { field_id: "f1", label: "Where is your land located? (State)", description: "Please select the state.", type: "dropdown", required: true, options: ["Gujarat", "Maharashtra", "Rajasthan"] },
          { field_id: "f2", label: "District / City", description: "Select the nearest city or district.", type: "dropdown", required: true, options: ["Ahmedabad", "Surat", "Mumbai", "Pune", "Jaipur", "Jodhpur"] },
          { field_id: "f3", label: "What is the total area of your land?", description: "In hectares", type: "number", required: true, options: null },
          { field_id: "f4", label: "What is the current land use?", description: "", type: "dropdown", required: true, options: ["Private agricultural land (patta/revenue land)", "Private fallow / degraded / wasteland", "Leased private land", "Recorded Forest Area / government forest", "Community / panchayat / commons land", "Grassland, scrub, open natural ecosystem"] },
          { field_id: "f5", label: "Do you have legal ownership documents?", description: "", type: "yes_no", required: true, options: null },
          { field_id: "f6", label: "Has the land been used for any carbon project before?", description: "", type: "yes_no", required: true, options: null },
          { field_id: "f7", label: "Upload relevant land documents", description: "PDF or Images", type: "file_upload", required: false, options: null }
        ]
      }
    ]
  },
  rules: {
    config_id: "default",
    rules: []
  },
  selectedFieldId: "f1",
  activeTab: "visual"
};

const fbIcons = {
  short_answer: `<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M17 3v18M3 15h14M3 9h14M3 3h14"/></svg>`,
  paragraph: `<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><line x1="21" y1="6" x2="3" y2="6"/><line x1="21" y1="12" x2="3" y2="12"/><line x1="21" y1="18" x2="3" y2="18"/></svg>`,
  number: `<span style="font-weight:bold">#</span>`,
  dropdown: `<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="3" y="3" width="18" height="18" rx="2" ry="2"/><line x1="3" y1="9" x2="21" y2="9"/><polyline points="9 14 12 17 15 14"/></svg>`,
  multiple_choice: `<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="10"/><circle cx="12" cy="12" r="3"/></svg>`,
  checkbox: `<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="3" y="3" width="18" height="18" rx="2" ry="2"/><polyline points="9 11 12 14 22 4"/></svg>`,
  date: `<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="3" y="4" width="18" height="18" rx="2" ry="2"/><line x1="16" y1="2" x2="16" y2="6"/><line x1="8" y1="2" x2="8" y2="6"/><line x1="3" y1="10" x2="21" y2="10"/></svg>`,
  email: `<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M4 4h16c1.1 0 2 .9 2 2v12c0 1.1-.9 2-2 2H4c-1.1 0-2-.9-2-2V6c0-1.1.9-2 2-2z"/><polyline points="22,6 12,13 2,6"/></svg>`,
  phone: `<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M22 16.92v3a2 2 0 0 1-2.18 2 19.79 19.79 0 0 1-8.63-3.07 19.5 19.5 0 0 1-6-6 19.79 19.79 0 0 1-3.07-8.67A2 2 0 0 1 4.11 2h3a2 2 0 0 1 2 1.72 12.84 12.84 0 0 0 .7 2.81 2 2 0 0 1-.45 2.11L8.09 9.91a16 16 0 0 0 6 6l1.27-1.27a2 2 0 0 1 2.11-.45 12.84 12.84 0 0 0 2.81.7A2 2 0 0 1 22 16.92z"/></svg>`,
  file_upload: `<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><polyline points="17 8 12 3 7 8"/><line x1="12" y1="3" x2="12" y2="15"/></svg>`,
  section_header: `<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M4 12h16M4 6h16M4 18h16"/></svg>`,
  divider: `<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><line x1="5" y1="12" x2="19" y2="12"/></svg>`,
  yes_no: `<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="20 6 9 17 4 12"/></svg>`,
  rating: `<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polygon points="12 2 15.09 8.26 22 9.27 17 14.14 18.18 21.02 12 17.77 5.82 21.02 7 14.14 2 9.27 8.91 8.26 12 2"/></svg>`,
  signature: `<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M12 20h9M16.5 3.5a2.121 2.121 0 0 1 3 3L7 19l-4 1 1-4L16.5 3.5z"/></svg>`
};

const fbLabels = {
  short_answer: "Short Answer",
  paragraph: "Paragraph",
  number: "Number",
  dropdown: "Dropdown",
  multiple_choice: "Multiple Choice",
  checkbox: "Checkbox",
  date: "Date",
  email: "Email",
  phone: "Phone",
  file_upload: "File Upload",
  section_header: "Section Header",
  divider: "Divider",
  yes_no: "Yes / No",
  rating: "Rating",
  signature: "Signature"
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
    { type: 'short_answer', label: 'Short Answer' },
    { type: 'paragraph', label: 'Paragraph' },
    { type: 'number', label: 'Number' },
    { type: 'dropdown', label: 'Dropdown' },
    { type: 'multiple_choice', label: 'Multiple Choice' },
    { type: 'checkbox', label: 'Checkbox' },
    { type: 'date', label: 'Date' },
    { type: 'email', label: 'Email' },
    { type: 'phone', label: 'Phone' },
  ];

  const advancedFields = [
    { type: 'file_upload', label: 'File Upload' },
    { type: 'section_header', label: 'Section Header' },
    { type: 'divider', label: 'Divider' },
    { type: 'yes_no', label: 'Yes / No' },
    { type: 'rating', label: 'Rating' },
    { type: 'signature', label: 'Signature' },
  ];

  palette.innerHTML = `
    <div class="fb-palette-category">Basic Fields</div>
    <div id="fb-palette-basic" class="fb-palette-list">
      ${basicFields.map(f => `
        <div class="fb-palette-item" data-type="${f.type}" onclick="fbAddField('${f.type}')">
          <span class="fb-palette-icon" style="display:flex; align-items:center; color: var(--accent);">${fbIcons[f.type]}</span>
          <span style="font-weight: 500;">${f.label}</span>
        </div>
      `).join('')}
    </div>
    
    <div class="fb-palette-category" style="margin-top: 24px;">Advanced Fields</div>
    <div id="fb-palette-advanced" class="fb-palette-list">
      ${advancedFields.map(f => `
        <div class="fb-palette-item" data-type="${f.type}" onclick="fbAddField('${f.type}')">
          <span class="fb-palette-icon" style="display:flex; align-items:center; color: var(--text-muted);">${fbIcons[f.type]}</span>
          <span style="font-weight: 500;">${f.label}</span>
        </div>
      `).join('')}
    </div>
  `;

  // Init Sortable for drag and drop
  if (typeof Sortable !== 'undefined') {
    Sortable.create(document.getElementById('fb-palette-basic'), {
      group: { name: 'fields', pull: 'clone', put: false },
      sort: false,
      animation: 150
    });
    Sortable.create(document.getElementById('fb-palette-advanced'), {
      group: { name: 'fields', pull: 'clone', put: false },
      sort: false,
      animation: 150
    });
  }
}

function fbRenderTabs() {
  const stepper = document.getElementById('fb-stepper');
  if (!stepper) return;

  stepper.innerHTML = `
    <div class="fb-step-wrap ${fbState.activeTab === 'visual' ? 'active' : ''}" onclick="fbSwitchTab('visual')">
      <div class="fb-step-num">1</div>
      <div style="display:flex; flex-direction:column; gap:2px;">
        <span style="font-weight:600; color:var(--text-primary);">Build</span>
        <span style="font-size:10px; color:var(--text-muted);">Create your form</span>
      </div>
    </div>
    <div class="fb-step-divider"></div>
    <div class="fb-step-wrap">
      <div class="fb-step-num">2</div>
      <div style="display:flex; flex-direction:column; gap:2px;">
        <span style="font-weight:600; color:var(--text-primary);">Configure</span>
        <span style="font-size:10px; color:var(--text-muted);">Form settings</span>
      </div>
    </div>
    <div class="fb-step-divider"></div>
    <div class="fb-step-wrap ${fbState.activeTab === 'json' ? 'active' : ''}" onclick="fbSwitchTab('json')">
      <div class="fb-step-num">3</div>
      <div style="display:flex; flex-direction:column; gap:2px;">
        <span style="font-weight:600; color:var(--text-primary);">Rules</span>
        <span style="font-size:10px; color:var(--text-muted);">Set evaluation rules</span>
      </div>
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
  if (field.type === 'short_answer' || field.type === 'email' || field.type === 'phone' || field.type === 'number') {
    return `<input type="text" class="fb-input-fake" placeholder="Enter answer..." disabled>`;
  }
  if (field.type === 'paragraph') {
    return `<textarea class="fb-input-fake" placeholder="Enter long answer..." rows="3" disabled></textarea>`;
  }
  if (field.type === 'dropdown' || field.type === 'multiple_choice' || field.type === 'checkbox') {
    const opts = (field.options && field.options.length > 0) ? field.options : ['Option 1', 'Option 2'];
    if (field.label && field.label.toLowerCase().includes('located')) {
       // Mock two-column dropdown for the image specific look
       return `
         <div class="fb-input-fake-row" style="margin-top:16px;">
           <div style="flex:1;">
             <label style="font-size:11px; font-weight:600; color:var(--text-primary); margin-bottom:6px; display:block;">State <span style="color:var(--error);">*</span></label>
             <select class="fb-input-fake" disabled><option>Select State</option></select>
           </div>
           <div style="flex:1;">
             <label style="font-size:11px; font-weight:600; color:var(--text-primary); margin-bottom:6px; display:block;">District <span style="color:var(--error);">*</span></label>
             <select class="fb-input-fake" disabled><option>Select District</option></select>
           </div>
         </div>
       `;
    }
    return `
      <select class="fb-input-fake" disabled>
        <option>${opts[0]}</option>
      </select>
    `;
  }
  if (field.type === 'yes_no') {
    return `
      <div class="fb-input-fake-row" style="margin-top:8px">
        <label><input type="radio" disabled> Yes</label>
        <label><input type="radio" disabled> No</label>
      </div>
    `;
  }
  if (field.type === 'date') return `<input type="date" class="fb-input-fake" disabled>`;
  if (field.type === 'file_upload') return `<div class="fb-add-zone" style="margin-top:8px; padding:24px; text-align:center; border: 1px dashed var(--border); border-radius: 6px; color:var(--text-muted); font-size:13px;">📁 Upload File</div>`;
  return '';
}

function fbRenderCanvas() {
  const canvas = document.getElementById('fb-canvas-content');
  if (!canvas) return;

  const step = fbState.schema.steps[0];

  let html = `
    <div class="fb-canvas-header" style="position:relative; text-align:center; padding: 24px 0 32px 0;">
      <div style="display:flex; justify-content:center; margin-bottom: 16px;">
        <svg width="32" height="32" viewBox="0 0 24 24" fill="none" stroke="var(--accent)" stroke-width="2"><path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"/><polyline points="9 12 11 14 15 10"/></svg>
      </div>
      <h2 style="font-size: 22px; font-weight: 700; color: var(--text-primary); display:flex; align-items:center; justify-content:center; gap:8px;">${step.title} <button class="fb-icon-btn" style="background:none;border:none;cursor:pointer;">✏️</button></h2>
      <p style="font-size: 14px; color: var(--text-secondary); max-width: 400px; margin: 8px auto 0 auto; line-height: 1.5;">${step.description}</p>
    </div>
    <div id="fb-canvas-list">
  `;

  step.fields.forEach((field, index) => {
    const isSelected = fbState.selectedFieldId === field.field_id;
    html += `
      <div class="fb-field-card ${isSelected ? 'selected' : ''}" onclick="fbSelectField('${field.field_id}')" data-id="${field.field_id}">
        <div class="fb-field-card-header">
          <div class="fb-drag-handle" style="color: #bbb; cursor: grab; margin-right: 8px;">
             <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="9" cy="5" r="1"/><circle cx="9" cy="12" r="1"/><circle cx="9" cy="19" r="1"/><circle cx="15" cy="5" r="1"/><circle cx="15" cy="12" r="1"/><circle cx="15" cy="19" r="1"/></svg>
          </div>
          <div class="fb-field-title" style="font-weight: 600; font-size: 14px; color: var(--text-primary); flex:1; display:flex; align-items:center;">
            ${index + 1}. ${field.label}
            ${field.required ? '<span class="fb-badge-required" style="color:#d93025; font-size:10px; font-weight:600; border:1px solid #fce8e6; background:transparent; padding:2px 6px; border-radius:12px; margin-left:8px;">Required</span>' : ''}
            <span class="fb-badge-step" style="background:#f3f4f6; font-size:10px; color:#6b7280; font-weight:600; padding:2px 6px; border-radius:12px; border:1px solid #e5e7eb; margin-left:8px;">Step ${index + 1}</span>
          </div>
          <div class="fb-field-actions">
            <button title="Duplicate" onclick="event.stopPropagation(); fbDuplicateField('${field.field_id}')">📄</button>
            <button class="delete" title="Delete" onclick="event.stopPropagation(); fbDeleteField('${field.field_id}')">🗑️</button>
            <button title="Expand" onclick="event.stopPropagation();">⌄</button>
          </div>
        </div>
        <div class="fb-field-preview" style="${isSelected ? 'display:block;' : 'display:none;'}">
          ${field.description ? `<div class="fb-field-description">${field.description}</div>` : ''}
          ${fbGetFieldInputPreview(field)}
        </div>
      </div>
    `;
  });

  html += `
    </div>
    <div class="fb-add-zone" onclick="fbAddField('short_answer')">
      + Drag a field here
    </div>
  `;

  canvas.innerHTML = html;
  fbRenderSettings();

  if (typeof Sortable !== 'undefined') {
    const listEl = document.getElementById('fb-canvas-list');
    if (listEl) {
      Sortable.create(listEl, {
        group: 'fields',
        animation: 150,
        handle: '.fb-drag-handle',
        onAdd: function (evt) {
          const type = evt.item.getAttribute('data-type');
          evt.item.remove();
          if (type) {
            fbAddField(type, evt.newIndex);
          }
        },
        onUpdate: function (evt) {
          const step = fbState.schema.steps[0];
          const item = step.fields.splice(evt.oldIndex, 1)[0];
          step.fields.splice(evt.newIndex, 0, item);
          fbRenderCanvas();
        }
      });
    }
  }
}
function fbAddField(type, index = -1) {
  const newField = {
    field_id: generateId(),
    label: 'New ' + (fbLabels[type] || 'Field'),
    type: type,
    required: false,
    description: '',
    options: (type === 'dropdown' || type === 'multiple_choice' || type === 'checkbox') ? ['Option 1', 'Option 2'] : null
  };
  
  if (index >= 0) {
    fbState.schema.steps[0].fields.splice(index, 0, newField);
  } else {
    fbState.schema.steps[0].fields.push(newField);
  }
  
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
      <div class="fb-tabs" style="display:flex; border-bottom:1px solid var(--border); padding:0 24px; margin-bottom:24px;">
        <div class="fb-tab active" style="flex:1; padding:16px 0; text-align:center; font-size:14px; font-weight:600; color:var(--accent); border-bottom:2px solid var(--accent); cursor:pointer;">Field Settings</div>
        <div class="fb-tab" style="flex:1; padding:16px 0; text-align:center; font-size:14px; font-weight:500; color:var(--text-secondary); cursor:pointer;">Form Settings</div>
      </div>
      <div style="text-align:center; padding: 32px 24px; color: var(--text-muted); font-size:13px;">
        Select a field to edit its settings
      </div>
    `;
    return;
  }

  const field = fbState.schema.steps[0].fields.find(f => f.field_id === fbState.selectedFieldId);
  if (!field) return;

  let optionsHtml = '';
  if (field.type === 'dropdown' || field.type === 'multiple_choice' || field.type === 'checkbox') {
    if (field.label && field.label.toLowerCase().includes('located')) {
      optionsHtml = `
        <div class="fb-settings-group" style="padding: 0 24px;">
          <div class="fb-settings-label" style="font-weight:600; font-size:13px; color:var(--text-primary); margin-bottom:12px;">Options</div>
          
          <div style="font-size:12px; color:var(--text-secondary); margin-bottom:8px;">Left Column</div>
          <div style="font-size:12px; font-weight:600; color:var(--text-primary); margin-bottom:8px;">State</div>
          <div class="fb-options-list" style="display:flex; flex-direction:column; gap:8px;">
            ${(field.options || []).map((opt, i) => `
              <div class="fb-option-item" style="display:flex; align-items:center; background:white; border:none; padding:4px 0;">
                <input type="text" value="${opt}" onchange="fbUpdateOptions(${i}, this.value)" style="border:none;background:transparent;width:100%;font-size:13px;outline:none;color:var(--text-primary);">
                <button style="background:none;border:none;color:var(--text-muted);cursor:pointer; font-size:14px;">✏️</button>
              </div>
            `).join('')}
          </div>
          <button class="fb-btn-link" style="color:var(--accent); background:none; border:none; font-size:13px; font-weight:600; cursor:pointer; padding:12px 0 24px 0;" onclick="fbAddOption()">+ Add Option</button>
          
          <div style="font-size:12px; color:var(--text-secondary); margin-bottom:8px;">Right Column</div>
          <div style="font-size:12px; font-weight:600; color:var(--text-primary); margin-bottom:8px;">District</div>
          <div class="fb-option-item" style="display:flex; align-items:center; background:white; border:none; padding:4px 0;">
             <input type="text" value="Dynamic based on state selection" disabled style="border:none;background:transparent;width:100%;font-size:13px;outline:none;color:var(--text-muted);">
             <button style="background:none;border:none;color:var(--text-muted);cursor:pointer; font-size:14px;">✏️</button>
          </div>
        </div>
        <hr style="border:0; border-top:1px solid var(--border); margin: 24px 0;">
      `;
    } else {
      optionsHtml = `
        <div class="fb-settings-group" style="padding: 0 24px;">
          <div class="fb-settings-label" style="font-weight:600; font-size:13px; color:var(--text-primary); margin-bottom:12px;">Options</div>
          <div class="fb-options-list" style="display:flex; flex-direction:column; gap:8px;">
            ${(field.options || []).map((opt, i) => `
              <div class="fb-option-item" style="display:flex; align-items:center; background:#f9fafb; border:1px solid var(--border); border-radius:6px; padding:8px 12px;">
                <div style="color:var(--text-muted); margin-right:8px; cursor:grab;">⋮⋮</div>
                <input type="text" value="${opt}" onchange="fbUpdateOptions(${i}, this.value)" style="border:none;background:transparent;width:100%;font-size:13px;outline:none;color:var(--text-primary);">
                <button style="background:none;border:none;color:var(--text-muted);cursor:pointer; font-size:16px;" onclick="fbRemoveOption(${i})">×</button>
              </div>
            `).join('')}
          </div>
          <button class="fb-btn-link" style="color:var(--accent); background:none; border:none; font-size:13px; font-weight:600; cursor:pointer; padding:12px 0 0 0;" onclick="fbAddOption()">+ Add Option</button>
        </div>
        <hr style="border:0; border-top:1px solid var(--border); margin: 24px 0;">
      `;
    }
  }

  sidebar.innerHTML = `
    <div class="fb-tabs" style="display:flex; border-bottom:1px solid var(--border); padding:0 24px; margin-bottom:24px;">
      <div class="fb-tab active" style="flex:1; padding:16px 0; text-align:center; font-size:14px; font-weight:600; color:var(--accent); border-bottom:2px solid var(--accent); cursor:pointer;">Field Settings</div>
      <div class="fb-tab" style="flex:1; padding:16px 0; text-align:center; font-size:14px; font-weight:500; color:var(--text-secondary); cursor:pointer;">Form Settings</div>
    </div>
    
    <div class="fb-settings-group" style="padding: 0 24px;">
      <div class="fb-settings-label" style="font-weight:600; font-size:15px; color:var(--text-primary); margin-bottom:16px;">General</div>
      
      <div class="fb-settings-field" style="margin-bottom:16px;">
        <label style="display:block; font-size:12px; color:var(--text-secondary); margin-bottom:6px; font-weight:500;">Label</label>
        <input type="text" value="${field.label}" onchange="fbUpdateSelectedField('label', this.value)" style="width:100%; padding:10px; border:1px solid var(--border); border-radius:6px; font-size:13px;">
      </div>
      
      <div class="fb-settings-field" style="margin-bottom:16px;">
        <label style="display:block; font-size:12px; color:var(--text-secondary); margin-bottom:6px; font-weight:500;">Description (Optional)</label>
        <textarea rows="2" onchange="fbUpdateSelectedField('description', this.value)" style="width:100%; padding:10px; border:1px solid var(--border); border-radius:6px; font-size:13px; font-family:inherit; resize:vertical;">${field.description || ''}</textarea>
      </div>
      
      <div class="fb-settings-field" style="margin-bottom:24px;">
        <label style="display:block; font-size:12px; color:var(--text-secondary); margin-bottom:6px; font-weight:500;">Field Type</label>
        <select onchange="fbUpdateSelectedField('type', this.value)" style="width:100%; padding:10px; border:1px solid var(--border); border-radius:6px; font-size:13px; background:white;">
          ${Object.keys(fbLabels).map(key => `<option value="${key}" ${field.type === key ? 'selected' : ''}>${fbLabels[key]}</option>`).join('')}
        </select>
      </div>
    </div>

    <hr style="border:0; border-top:1px solid var(--border); margin: 0 0 24px 0;">

    <div class="fb-settings-group" style="padding: 0 24px;">
      <div class="fb-toggle-row" style="display:flex; justify-content:space-between; align-items:center; margin-bottom:16px;">
        <span style="font-size:13px; font-weight:500; color:var(--text-primary);">Required Field</span>
        <label class="fb-toggle">
          <input type="checkbox" ${field.required ? 'checked' : ''} onchange="fbUpdateSelectedField('required', this.checked)">
          <span class="fb-toggle-slider"></span>
        </label>
      </div>
      <div class="fb-toggle-row" style="display:flex; justify-content:space-between; align-items:center; margin-bottom:24px;">
        <span style="font-size:13px; font-weight:500; color:var(--text-primary);">Show in Summary</span>
        <label class="fb-toggle">
          <input type="checkbox" checked>
          <span class="fb-toggle-slider"></span>
        </label>
      </div>
    </div>

    <hr style="border:0; border-top:1px solid var(--border); margin: 0 0 24px 0;">

    ${optionsHtml}

    <div class="fb-settings-group" style="padding: 0 24px 32px 24px;">
      <div class="fb-settings-label" style="font-weight:600; font-size:15px; color:var(--text-primary); margin-bottom:16px;">Advanced</div>
      <div style="font-size:13px; font-weight:500; color:var(--text-primary); margin-bottom:8px;">Conditional Logic</div>
      <div style="display:flex; justify-content:space-between; align-items:center;">
         <span style="font-size:13px; color:var(--text-secondary);">Add condition</span>
         <span style="color:var(--text-muted);">></span>
      </div>
    </div>
  `;
}

// Intercept
async function fbSaveToServer() {
  try {
    // If we are in JSON view, sync back to visual state first just in case they edited JSON directly
    if (fbState.activeTab === 'json') {
      fbState.schema = JSON.parse(document.getElementById('json-form-schema').value);
      fbState.rules = JSON.parse(document.getElementById('json-eval-rules').value);
    }
    
    let res = await fetch(`${API_BASE}/api/admin/form/form-schema`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json', ...authHeader() },
      body: JSON.stringify(fbState.schema)
    });
    if (!res.ok) throw new Error('Failed to save schema');

    res = await fetch(`${API_BASE}/api/admin/form/eval-config`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json', ...authHeader() },
      body: JSON.stringify(fbState.rules)
    });
    if (!res.ok) throw new Error('Failed to save rules');

    toast('✅ Form & Rules saved successfully', 'ok');
  } catch (e) {
    toast(`❌ ${e.message}`, 'err');
  }
}

// Override the original loadFormConfig to populate fbState instead of just textareas
async function loadFormConfig() {
  try {
    const schemaRes = await fetch(`${API_BASE}/api/admin/form/form-schema`, { headers: authHeader() });
    const rulesRes = await fetch(`${API_BASE}/api/admin/form/eval-config`, { headers: authHeader() });
    
    if (schemaRes.ok) {
      let fetchedSchema = await schemaRes.json();
      if (fetchedSchema && fetchedSchema.steps && fetchedSchema.steps.length > 0 && fetchedSchema.steps[0].fields && fetchedSchema.steps[0].fields.length > 0) {
        fbState.schema = fetchedSchema;
      }
    }
    if (rulesRes.ok) fbState.rules = await rulesRes.json();
  } catch (e) {
    console.error('Failed to load form config', e);
  } finally {
    fbInit();
  }
}
