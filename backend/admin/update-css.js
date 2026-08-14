const fs = require('fs');
let css = fs.readFileSync('form-builder.css', 'utf8');
const toggleCss = `
/* Toggle Switch */
.fb-toggle {
  position: relative;
  display: inline-block;
  width: 36px;
  height: 20px;
}
.fb-toggle input { 
  opacity: 0;
  width: 0;
  height: 0;
}
.fb-toggle-slider {
  position: absolute;
  cursor: pointer;
  top: 0; left: 0; right: 0; bottom: 0;
  background-color: #ccc;
  transition: .4s;
  border-radius: 34px;
}
.fb-toggle-slider:before {
  position: absolute;
  content: "";
  height: 16px;
  width: 16px;
  left: 2px;
  bottom: 2px;
  background-color: white;
  transition: .4s;
  border-radius: 50%;
}
input:checked + .fb-toggle-slider {
  background-color: var(--accent);
}
input:checked + .fb-toggle-slider:before {
  transform: translateX(16px);
}

/* Updated Field Card */
.fb-field-card {
  background: white;
  border: 1px solid var(--border);
  border-radius: 8px;
  padding: 16px;
  margin-bottom: 12px;
  box-shadow: 0 1px 2px rgba(0,0,0,0.02);
  transition: all 0.2s ease;
  position: relative;
}
.fb-field-card:hover {
  border-color: #d1d5db;
  box-shadow: 0 2px 4px rgba(0,0,0,0.05);
}
.fb-field-card.selected {
  border-color: #059669; /* Green border for selected state */
  box-shadow: 0 0 0 1px #059669, 0 2px 4px rgba(0,0,0,0.05);
}
`;

if (!css.includes('.fb-toggle {')) {
  css += toggleCss;
  fs.writeFileSync('form-builder.css', css);
  console.log('Added toggles and updated card CSS');
}
