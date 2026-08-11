import os
import json
from fastapi import APIRouter, UploadFile, File, Form, HTTPException
from pydantic import BaseModel
from typing import Optional

router = APIRouter()

class GEEConfig(BaseModel):
    service_account_json: str

# Mock storage for config (in production this goes to DB or secure Vault)
_gee_config: Optional[str] = None
_gee_valid: bool = False
_one_geojson_path: Optional[str] = None

@router.get("/geospatial/status")
async def get_geospatial_status():
    """Returns the comprehensive status of geospatial configurations."""
    return {
        "gee_configured": _gee_config is not None,
        "gee_valid": _gee_valid,
        "bhuvan_available": True, # Public WMS
        "one_data_loaded": _one_geojson_path is not None,
        "features_active": _gee_valid and (_one_geojson_path is not None)
    }

@router.get("/geospatial/config")
async def get_geospatial_config():
    """Legacy endpoint, keeping for compatibility if needed."""
    return {
        "gee_configured": _gee_config is not None,
        "one_data_configured": _one_geojson_path is not None
    }

@router.post("/geospatial/gee-key")
async def upload_gee_key(config: GEEConfig):
    """
    Accepts a GEE service account JSON string and stores it.
    """
    global _gee_config
    if not config.service_account_json:
        raise HTTPException(status_code=400, detail="No JSON provided")
        
    # Validate JSON structure as a basic check
    try:
        json.loads(config.service_account_json)
        _gee_valid = True
    except Exception:
        _gee_valid = False
        raise HTTPException(status_code=400, detail="Invalid JSON format for Service Account")
        
    _gee_config = config.service_account_json
    return {"status": "success", "message": "GEE Service Account Key configured and validated."}

@router.post("/geospatial/one-data")
async def upload_one_data(file: UploadFile = File(...)):
    """
    Accepts a GeoJSON file for the Open Natural Ecosystem (ONE) layer.
    """
    global _one_geojson_path
    if not file.filename.endswith('.json') and not file.filename.endswith('.geojson'):
        raise HTTPException(status_code=400, detail="Must be a .json or .geojson file")
        
    content = await file.read()
    
    # Save to a local temp path for the mock (in production we'd load to PostGIS `ST_GeomFromGeoJSON`)
    save_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "geospatial", "data")
    os.makedirs(save_dir, exist_ok=True)
    
    file_path = os.path.join(save_dir, "one_layer.geojson")
    with open(file_path, "wb") as f:
        f.write(content)
        
    _one_geojson_path = file_path
    
    return {"status": "success", "message": f"ONE GeoJSON {file.filename} uploaded and processed."}
