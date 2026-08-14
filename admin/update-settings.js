const fs = require('fs');

let code = fs.readFileSync('form-builder.js', 'utf8');

const start = code.indexOf('function fbRenderSettings');
const end = code.indexOf('async function fbSaveToServer');

const oldFunc = code.substring(start, end);

const newFunc = `function fbRenderSettings() {
  const sidebar = document.getElementById('fb-settings');
  if (!sidebar) return;

  if (!fbState.selectedFieldId) {
    sidebar.innerHTML = \`
      <div class="fb-tabs" style="display:flex; border-bottom:1px solid var(--border); padding:0 24px; margin-bottom:24px;">
        <div class="fb-tab active" style="flex:1; padding:16px 0; text-align:center; font-size:14px; font-weight:600; color:var(--accent); border-bottom:2px solid var(--accent); cursor:pointer;">Field Settings</div>
        <div class="fb-tab" style="flex:1; padding:16px 0; text-align:center; font-size:14px; font-weight:500; color:var(--text-secondary); cursor:pointer;">Form Settings</div>
      </div>
      <div style="text-align:center; padding: 32px 24px; color: var(--text-muted); font-size:13px;">
        Select a field to edit its settings
      </div>
    \`;
    return;
  }

  const field = fbState.schema.steps[0].fields.find(f => f.field_id === fbState.selectedFieldId);
  if (!field) return;

  let optionsHtml = '';
  if (field.type === 'dropdown' || field.type === 'multiple_choice' || field.type === 'checkbox') {
    if (field.label.toLowerCase().includes('located')) {
      optionsHtml = \`
        <div class="fb-settings-group" style="padding: 0 24px;">
          <div class="fb-settings-label" style="font-weight:600; font-size:13px; color:var(--text-primary); margin-bottom:12px;">Options</div>
          
          <div style="font-size:12px; color:var(--text-secondary); margin-bottom:8px;">Left Column</div>
          <div style="font-size:12px; font-weight:600; color:var(--text-primary); margin-bottom:8px;">State</div>
          <div class="fb-options-list" style="display:flex; flex-direction:column; gap:8px;">
            \${(field.options || []).map((opt, i) => \`
              <div class="fb-option-item" style="display:flex; align-items:center; background:white; border:none; padding:4px 0;">
                <input type="text" value="\${opt}" onchange="fbUpdateOptions(\${i}, this.value)" style="border:none;background:transparent;width:100%;font-size:13px;outline:none;color:var(--text-primary);">
                <button style="background:none;border:none;color:var(--text-muted);cursor:pointer; font-size:14px;">✏️</button>
              </div>
            \`).join('')}
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
      \`;
    } else {
      optionsHtml = \`
        <div class="fb-settings-group" style="padding: 0 24px;">
          <div class="fb-settings-label" style="font-weight:600; font-size:13px; color:var(--text-primary); margin-bottom:12px;">Options</div>
          <div class="fb-options-list" style="display:flex; flex-direction:column; gap:8px;">
            \${(field.options || []).map((opt, i) => \`
              <div class="fb-option-item" style="display:flex; align-items:center; background:#f9fafb; border:1px solid var(--border); border-radius:6px; padding:8px 12px;">
                <div style="color:var(--text-muted); margin-right:8px; cursor:grab;">⋮⋮</div>
                <input type="text" value="\${opt}" onchange="fbUpdateOptions(\${i}, this.value)" style="border:none;background:transparent;width:100%;font-size:13px;outline:none;color:var(--text-primary);">
                <button style="background:none;border:none;color:var(--text-muted);cursor:pointer; font-size:16px;" onclick="fbRemoveOption(\${i})">×</button>
              </div>
            \`).join('')}
          </div>
          <button class="fb-btn-link" style="color:var(--accent); background:none; border:none; font-size:13px; font-weight:600; cursor:pointer; padding:12px 0 0 0;" onclick="fbAddOption()">+ Add Option</button>
        </div>
        <hr style="border:0; border-top:1px solid var(--border); margin: 24px 0;">
      \`;
    }
  }

  sidebar.innerHTML = \`
    <div class="fb-tabs" style="display:flex; border-bottom:1px solid var(--border); padding:0 24px; margin-bottom:24px;">
      <div class="fb-tab active" style="flex:1; padding:16px 0; text-align:center; font-size:14px; font-weight:600; color:var(--accent); border-bottom:2px solid var(--accent); cursor:pointer;">Field Settings</div>
      <div class="fb-tab" style="flex:1; padding:16px 0; text-align:center; font-size:14px; font-weight:500; color:var(--text-secondary); cursor:pointer;">Form Settings</div>
    </div>
    
    <div class="fb-settings-group" style="padding: 0 24px;">
      <div class="fb-settings-label" style="font-weight:600; font-size:15px; color:var(--text-primary); margin-bottom:16px;">General</div>
      
      <div class="fb-settings-field" style="margin-bottom:16px;">
        <label style="display:block; font-size:12px; color:var(--text-secondary); margin-bottom:6px; font-weight:500;">Label</label>
        <input type="text" value="\${field.label}" onchange="fbUpdateSelectedField('label', this.value)" style="width:100%; padding:10px; border:1px solid var(--border); border-radius:6px; font-size:13px;">
      </div>
      
      <div class="fb-settings-field" style="margin-bottom:16px;">
        <label style="display:block; font-size:12px; color:var(--text-secondary); margin-bottom:6px; font-weight:500;">Description (Optional)</label>
        <textarea rows="2" onchange="fbUpdateSelectedField('description', this.value)" style="width:100%; padding:10px; border:1px solid var(--border); border-radius:6px; font-size:13px; font-family:inherit; resize:vertical;">\${field.description || ''}</textarea>
      </div>
      
      <div class="fb-settings-field" style="margin-bottom:24px;">
        <label style="display:block; font-size:12px; color:var(--text-secondary); margin-bottom:6px; font-weight:500;">Field Type</label>
        <select onchange="fbUpdateSelectedField('type', this.value)" style="width:100%; padding:10px; border:1px solid var(--border); border-radius:6px; font-size:13px; background:white;">
          \${Object.keys(fbLabels).map(key => \`<option value="\${key}" \${field.type === key ? 'selected' : ''}>\${fbLabels[key]}</option>\`).join('')}
        </select>
      </div>
    </div>

    <hr style="border:0; border-top:1px solid var(--border); margin: 0 0 24px 0;">

    <div class="fb-settings-group" style="padding: 0 24px;">
      <div class="fb-toggle-row" style="display:flex; justify-content:space-between; align-items:center; margin-bottom:16px;">
        <span style="font-size:13px; font-weight:500; color:var(--text-primary);">Required Field</span>
        <label class="fb-toggle">
          <input type="checkbox" \${field.required ? 'checked' : ''} onchange="fbUpdateSelectedField('required', this.checked)">
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

    \${optionsHtml}

    <div class="fb-settings-group" style="padding: 0 24px 32px 24px;">
      <div class="fb-settings-label" style="font-weight:600; font-size:15px; color:var(--text-primary); margin-bottom:16px;">Advanced</div>
      <div style="font-size:13px; font-weight:500; color:var(--text-primary); margin-bottom:8px;">Conditional Logic</div>
      <div style="display:flex; justify-content:space-between; align-items:center;">
         <span style="font-size:13px; color:var(--text-secondary);">Add condition</span>
         <span style="color:var(--text-muted);">></span>
      </div>
    </div>
  \`;
}

// Intercept`;

code = code.replace(oldFunc, newFunc);
fs.writeFileSync('form-builder.js', code);
console.log('Done settings');
