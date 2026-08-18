import asyncio
from motor.motor_asyncio import AsyncIOMotorClient

async def update():
    # Connect to MongoDB
    client = AsyncIOMotorClient("mongodb://localhost:27017")
    db = client.envirowealth
    
    schema = {
        "schema_id": "default",
        "version": 1,
        "steps": [
          {
            "step_id": "s1",
            "title": "1. Where is your land located?",
            "description": "Please provide the state and district of your land.",
            "fields": [
              { "field_id": "state", "label": "State", "type": "dropdown", "required": True, "options": ["Gujarat", "Maharashtra", "Rajasthan"] },
              { "field_id": "district", "label": "District", "type": "dropdown", "required": True, "options": ["Ahmedabad", "Surat", "Mumbai", "Pune", "Jaipur", "Jodhpur"] }
            ]
          },
          {
            "step_id": "s2",
            "title": "2. How large is the land?",
            "description": "The economics of carbon projects depend heavily on scale.",
            "fields": [
              { "field_id": "area_ha", "label": "Area (in Hectares)", "type": "number", "required": True, "placeholder": "e.g. 5", "options": None }
            ]
          },
          {
            "step_id": "s3",
            "title": "3. What is your tenure status?",
            "description": "Tenure affects who holds the carbon rights.",
            "fields": [
              { "field_id": "tenure_type", "label": "Tenure Type", "type": "dropdown", "required": True, "options": ["Owned Outright", "Leased", "Community / Panchayat Land", "Government-granted", "Disputed"] }
            ]
          },
          {
            "step_id": "s4",
            "title": "4. Land Legal Classification",
            "description": "Planting on recorded forest land is generally ineligible.",
            "fields": [
              { "field_id": "land_legal_class", "label": "Legal Classification", "type": "dropdown", "required": True, "options": ["Revenue Fallow", "Revenue Agricultural", "Recorded Forest", "Wasteland"] }
            ]
          },
          {
            "step_id": "s5",
            "title": "5. Existing Tree Cover",
            "description": "Roughly what percentage of your land currently has tree cover?",
            "fields": [
              { "field_id": "existing_tree_cover_pct", "label": "Tree Cover Percentage (0-100%)", "type": "number", "required": True, "placeholder": "e.g. 10", "options": None }
            ]
          },
          {
            "step_id": "s6",
            "title": "6. Planting & Additionality",
            "description": "",
            "fields": [
              { "field_id": "planting_status", "label": "Have you already started planting trees?", "type": "dropdown", "required": True, "options": ["Not started yet", "Planning to plant this year", "Planted within the last 2-5 years", "Planted more than 5 years ago"] },
              { "field_id": "would_plant_anyway", "label": "Would you plant trees even without carbon credit income?", "type": "yes_no", "required": True, "options": None }
            ]
          }
        ]
    }
    
    rules = {
        "config_id": "default",
        "rules": [
            { "rule_id": "r1", "target_field": "tenure_type", "operator": "in", "target_value": ["Disputed", "Government-granted"], "action": "fail_structural", "reason": "Disputed or government land is ineligible.", "flags": ["gate_5"] },
            { "rule_id": "r2", "target_field": "land_legal_class", "operator": "eq", "target_value": "Recorded Forest", "action": "fail_structural", "reason": "Recorded forest land requires specific government pathways.", "flags": ["forest_dept_redirect"] },
            { "rule_id": "r3", "target_field": "existing_tree_cover_pct", "operator": "gt", "target_value": 20, "action": "flag", "reason": "High existing tree cover may face additionality or forest-status issues.", "flags": ["gate_1"] },
            { "rule_id": "r4", "target_field": "planting_status", "operator": "eq", "target_value": "Planted more than 5 years ago", "action": "fail_structural", "reason": "Trees planted over 5 years ago are generally ineligible for new registration.", "flags": ["gate_3"] },
            { "rule_id": "r5", "target_field": "would_plant_anyway", "operator": "eq", "target_value": "Yes", "action": "flag", "reason": "Potential additionality concern.", "flags": ["gate_4"] }
        ]
    }

    await db.form_schemas.update_one({"schema_id": "default"}, {"$set": schema}, upsert=True)
    await db.evaluation_configs.update_one({"config_id": "default"}, {"$set": rules}, upsert=True)
    
    print("Successfully updated MongoDB schema and rules.")

if __name__ == "__main__":
    asyncio.run(update())
