from pydantic import BaseModel, Field
from typing import List, Optional, Any
from enum import Enum
from datetime import datetime

class FieldType(str, Enum):
    text = "text"
    number = "number"
    select = "select"
    boolean = "boolean"
    short_answer = "short_answer"
    paragraph = "paragraph"
    dropdown = "dropdown"
    multiple_choice = "multiple_choice"
    checkbox = "checkbox"
    date = "date"
    email = "email"
    phone = "phone"
    file_upload = "file_upload"
    section_header = "section_header"
    divider = "divider"
    yes_no = "yes_no"
    rating = "rating"
    signature = "signature"

class FormField(BaseModel):
    field_id: str
    label: str
    type: FieldType
    options: Optional[List[str]] = None
    required: bool = True
    placeholder: Optional[str] = None
    description: Optional[str] = None

class FormStep(BaseModel):
    step_id: str
    title: str
    description: Optional[str] = None
    fields: List[FormField] = []

class FormSchema(BaseModel):
    schema_id: str = "default"
    version: int = 1
    steps: List[FormStep] = []
    updated_at: datetime = Field(default_factory=datetime.utcnow)

class RuleOperator(str, Enum):
    eq = "eq"
    neq = "neq"
    gt = "gt"
    lt = "lt"
    gte = "gte"
    lte = "lte"
    in_ = "in"
    not_in = "not_in"

class RuleAction(str, Enum):
    fail_structural = "fail_structural"
    flag = "flag"

class EvaluationRule(BaseModel):
    rule_id: str
    target_field: str
    operator: RuleOperator
    target_value: Any
    action: RuleAction
    reason: str
    flags: List[str] = []

class EvaluationConfig(BaseModel):
    config_id: str = "default"
    rules: List[EvaluationRule] = []
    updated_at: datetime = Field(default_factory=datetime.utcnow)
