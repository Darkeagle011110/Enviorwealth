const fs = require('fs');

let code = fs.readFileSync('form-builder.js', 'utf8');

const start = code.indexOf('function fbGetFieldInputPreview');
const end = code.indexOf('function fbAddField');

const oldFuncs = code.substring(start, end);

const newFuncs = `function fbGetFieldInputPreview(field) {
  if (field.type === 'short_answer' || field.type === 'email' || field.type === 'phone' || field.type === 'number') {
    return \`<input type="text" class="fb-input-fake" placeholder="Enter answer..." disabled>\`;
  }
  if (field.type === 'paragraph') {
    return \`<textarea class="fb-input-fake" placeholder="Enter long answer..." rows="3" disabled></textarea>\`;
  }
  if (field.type === 'dropdown' || field.type === 'multiple_choice' || field.type === 'checkbox') {
    const opts = (field.options && field.options.length > 0) ? field.options : ['Option 1', 'Option 2'];
    if (field.label.toLowerCase().includes('located')) {
       // Mock two-column dropdown for the image specific look
       return \`
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
       \`;
    }
    return \`
      <select class="fb-input-fake" disabled>
        <option>\${opts[0]}</option>
      </select>
    \`;
  }
  if (field.type === 'yes_no') {
    return \`
      <div class="fb-input-fake-row" style="margin-top:8px">
        <label><input type="radio" disabled> Yes</label>
        <label><input type="radio" disabled> No</label>
      </div>
    \`;
  }
  if (field.type === 'date') return \`<input type="date" class="fb-input-fake" disabled>\`;
  if (field.type === 'file_upload') return \`<div class="fb-add-zone" style="margin-top:8px; padding:24px; text-align:center; border: 1px dashed var(--border); border-radius: 6px; color:var(--text-muted); font-size:13px;">📁 Upload File</div>\`;
  return '';
}

function fbRenderCanvas() {
  const canvas = document.getElementById('fb-canvas-content');
  if (!canvas) return;

  const step = fbState.schema.steps[0];

  let html = \`
    <div class="fb-canvas-header" style="position:relative; text-align:center; padding: 24px 0 32px 0;">
      <div style="display:flex; justify-content:center; margin-bottom: 16px;">
        <svg width="32" height="32" viewBox="0 0 24 24" fill="none" stroke="var(--accent)" stroke-width="2"><path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"/><polyline points="9 12 11 14 15 10"/></svg>
      </div>
      <h2 style="font-size: 22px; font-weight: 700; color: var(--text-primary); display:flex; align-items:center; justify-content:center; gap:8px;">\${step.title} <button class="fb-icon-btn" style="background:none;border:none;cursor:pointer;">✏️</button></h2>
      <p style="font-size: 14px; color: var(--text-secondary); max-width: 400px; margin: 8px auto 0 auto; line-height: 1.5;">\${step.description}</p>
    </div>
    <div id="fb-canvas-list">
  \`;

  step.fields.forEach((field, index) => {
    const isSelected = fbState.selectedFieldId === field.field_id;
    html += \`
      <div class="fb-field-card \${isSelected ? 'selected' : ''}" onclick="fbSelectField('\${field.field_id}')" data-id="\${field.field_id}">
        <div class="fb-field-card-header">
          <div class="fb-drag-handle" style="color: #bbb; cursor: grab; margin-right: 8px;">
             <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="9" cy="5" r="1"/><circle cx="9" cy="12" r="1"/><circle cx="9" cy="19" r="1"/><circle cx="15" cy="5" r="1"/><circle cx="15" cy="12" r="1"/><circle cx="15" cy="19" r="1"/></svg>
          </div>
          <div class="fb-field-title" style="font-weight: 600; font-size: 14px; color: var(--text-primary); flex:1; display:flex; align-items:center;">
            \${index + 1}. \${field.label}
            \${field.required ? '<span class="fb-badge-required" style="color:#d93025; font-size:10px; font-weight:600; border:1px solid #fce8e6; background:transparent; padding:2px 6px; border-radius:12px; margin-left:8px;">Required</span>' : ''}
            <span class="fb-badge-step" style="background:#f3f4f6; font-size:10px; color:#6b7280; font-weight:600; padding:2px 6px; border-radius:12px; border:1px solid #e5e7eb; margin-left:8px;">Step \${index + 1}</span>
          </div>
          <div class="fb-field-actions">
            <button title="Duplicate" onclick="event.stopPropagation(); fbDuplicateField('\${field.field_id}')">📄</button>
            <button class="delete" title="Delete" onclick="event.stopPropagation(); fbDeleteField('\${field.field_id}')">🗑️</button>
            <button title="Expand" onclick="event.stopPropagation();">⌄</button>
          </div>
        </div>
        <div class="fb-field-preview" style="\${isSelected ? 'display:block;' : 'display:none;'}">
          \${field.description ? \`<div class="fb-field-description">\${field.description}</div>\` : ''}
          \${fbGetFieldInputPreview(field)}
        </div>
      </div>
    \`;
  });

  html += \`
    </div>
    <div class="fb-add-zone" onclick="fbAddField('short_answer')">
      + Drag a field here
    </div>
  \`;

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
`;

code = code.replace(oldFuncs, newFuncs);
fs.writeFileSync('form-builder.js', code);
console.log('Done canvas rendering');
