const fs = require('fs');

let code = fs.readFileSync('form-builder.js', 'utf8');

const newInitialState = `let fbState = {
  schema: {
    schema_id: "default",
    version: 1,
    steps: [
      {
        step_id: "step_1",
        title: "Check Your Land Eligibility",
        description: "Answer a few quick questions and get a preliminary assessment of your land's eligibility for carbon credits.",
        fields: [
          { field_id: "f1", label: "Where is your land located?", description: "Please provide the state and district of your land.", type: "dropdown", required: true, options: ["Andhra Pradesh", "Karnataka", "Maharashtra", "Tamil Nadu"] },
          { field_id: "f2", label: "What is the total area of your land?", description: "", type: "number", required: false, options: null },
          { field_id: "f3", label: "What is the current land use?", description: "", type: "dropdown", required: false, options: ["Private agricultural land (patta/revenue land)", "Private fallow / degraded / wasteland", "Leased private land", "Recorded Forest Area / government forest", "Community / panchayat / commons land", "Grassland, scrub, open natural ecosystem"] },
          { field_id: "f4", label: "Do you have legal ownership documents?", description: "", type: "yes_no", required: false, options: null },
          { field_id: "f5", label: "Has the land been used for any carbon project before?", description: "", type: "yes_no", required: false, options: null },
          { field_id: "f6", label: "Upload relevant land documents", description: "", type: "file_upload", required: false, options: null }
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
};`;

code = code.replace(/let fbState = \{[\s\S]*?activeTab: "visual" \/\/ 'visual' or 'json'\n\};/, newInitialState);

// Replace fallback in loadFormConfig
const oldFallback = `    if (schemaRes.ok) fbState.schema = await schemaRes.json();
    if (rulesRes.ok) fbState.rules = await rulesRes.json();`;

const newFallback = `    if (schemaRes.ok) {
      let fetchedSchema = await schemaRes.json();
      if (fetchedSchema.steps && fetchedSchema.steps[0].fields.length > 0) {
        fbState.schema = fetchedSchema;
      }
    }
    if (rulesRes.ok) fbState.rules = await rulesRes.json();`;
    
code = code.replace(oldFallback, newFallback);


fs.writeFileSync('form-builder.js', code);
console.log('Done fbState');
