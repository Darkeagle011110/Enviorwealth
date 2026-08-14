const fs = require('fs');
let css = fs.readFileSync('form-builder.css', 'utf8');
const cardCss = `
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
  cursor: pointer;
}
.fb-field-card:hover {
  border-color: #d1d5db;
  box-shadow: 0 2px 4px rgba(0,0,0,0.05);
}
.fb-field-card.selected {
  border-color: #059669;
  box-shadow: 0 0 0 1px #059669, 0 2px 4px rgba(0,0,0,0.05);
}
`;
if (!css.includes('.fb-field-card {')) {
  css += cardCss;
  fs.writeFileSync('form-builder.css', css);
  console.log('Added card css');
}
