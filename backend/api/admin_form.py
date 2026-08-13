import logging
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import ValidationError
from motor.motor_asyncio import AsyncIOMotorDatabase
from typing import Dict, Any

from models.mongodb import get_db
from models.form_config import FormSchema, EvaluationConfig

logger = logging.getLogger(__name__)

router = APIRouter()

@router.get("/form-schema", response_model=FormSchema)
async def get_form_schema(db: AsyncIOMotorDatabase = Depends(get_db)):
    """Fetch the active dynamic form schema."""
    doc = await db.form_schemas.find_one({"schema_id": "default"})
    if not doc:
        # Return an empty default schema if none exists
        return FormSchema()
    return FormSchema(**doc)


@router.put("/form-schema", response_model=FormSchema)
async def update_form_schema(
    schema: FormSchema,
    db: AsyncIOMotorDatabase = Depends(get_db)
):
    """Update or create the dynamic form schema."""
    doc = schema.model_dump()
    result = await db.form_schemas.update_one(
        {"schema_id": schema.schema_id},
        {"$set": doc},
        upsert=True
    )
    return schema


@router.get("/eval-config", response_model=EvaluationConfig)
async def get_eval_config(db: AsyncIOMotorDatabase = Depends(get_db)):
    """Fetch the active evaluation configuration."""
    doc = await db.evaluation_configs.find_one({"config_id": "default"})
    if not doc:
        return EvaluationConfig()
    return EvaluationConfig(**doc)


@router.put("/eval-config", response_model=EvaluationConfig)
async def update_eval_config(
    config: EvaluationConfig,
    db: AsyncIOMotorDatabase = Depends(get_db)
):
    """Update or create the evaluation configuration."""
    doc = config.model_dump()
    result = await db.evaluation_configs.update_one(
        {"config_id": config.config_id},
        {"$set": doc},
        upsert=True
    )
    return config
