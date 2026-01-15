import re
from typing import Optional
import phonenumbers
from datetime import datetime
from pydantic import BaseModel, Field, field_validator, ValidationInfo, ConfigDict

class WebhookPayload(BaseModel):
    message_id: str = Field(..., min_length=1)
    from_msisdn: str = Field(..., alias="from")
    to_msisdn: str = Field(..., alias="to")
    ts: str
    text: Optional[str] = Field(None, max_length=4096)

    @field_validator("from_msisdn", "to_msisdn")
    @classmethod
    def validate_e164(cls, v: str, info: ValidationInfo) -> str:
        if not re.match(r"^\+[1-9]\d{1,14}$", v):
             raise ValueError("Must be E.164 format (e.g. +14155550100)")
        
        try:
            parsed = phonenumbers.parse(v, None)
            if not phonenumbers.is_valid_number(parsed):
                raise ValueError("Invalid phone number")
        except phonenumbers.NumberParseException:
             raise ValueError("Could not parse phone number")
        
        return v

    @field_validator("ts")
    @classmethod
    def validate_iso8601(cls, v: str) -> str:
        if not v.endswith("Z"):
            raise ValueError("Timestamp must be UTC ISO-8601 ending with 'Z'")
        try:
            datetime.fromisoformat(v.replace("Z", "+00:00"))
        except ValueError:
            raise ValueError("Invalid ISO-8601 timestamp")
        return v

class MessageResponse(BaseModel):
    message_id: str
    from_: str = Field(..., alias="from_msisdn", serialization_alias="from")
    to: str = Field(..., alias="to_msisdn", serialization_alias="to")
    ts: str
    text: Optional[str] = None
    
    model_config = ConfigDict(from_attributes=True, populate_by_name=True)