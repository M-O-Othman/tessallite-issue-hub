from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import List, Dict, Any, Optional

from issue_hub.database import get_db
from issue_hub.auth import verify_api_token
from issue_hub.models import LookupValue, HubSetting

router = APIRouter(prefix="/api/v1/config", tags=["Configuration"])

class LookupValueSchema(BaseModel):
    value: str
    label: Optional[str] = None
    display_order: int = 0
    is_active: bool = True
    is_terminal: Optional[bool] = None
    metadata: Dict[str, Any] = {}

class LookupListResponse(BaseModel):
    ok: bool
    items: List[LookupValueSchema]

class SettingUpdateSchema(BaseModel):
    setting_key: str
    setting_value: Dict[str, Any]

@router.get("/lookups/{lookup_type}", response_model=LookupListResponse)
def api_get_lookups(
    lookup_type: str,
    db: Session = Depends(get_db),
    token: str = Depends(verify_api_token)
):
    """Retrieve lookup vocabularies for a specific type (e.g. STATUS, SEVERITY)."""
    values = db.query(LookupValue).filter(
        LookupValue.lookup_type == lookup_type.upper()
    ).order_by(LookupValue.display_order.asc(), LookupValue.value.asc()).all()
    
    items = []
    for v in values:
        items.append({
            "value": v.value,
            "label": v.label,
            "display_order": v.display_order,
            "is_active": v.is_active,
            "is_terminal": v.is_terminal,
            "metadata": v.metadata_ or {}
        })
        
    return {"ok": True, "items": items}

@router.put("/lookups/{lookup_type}", response_model=LookupListResponse)
def api_save_lookups(
    lookup_type: str,
    request: List[LookupValueSchema],
    db: Session = Depends(get_db),
    token: str = Depends(verify_api_token)
):
    """Save (overwrite) lookup vocabularies for a specific type."""
    type_upper = lookup_type.upper()
    
    # Overwrite within a transaction
    db.query(LookupValue).filter(LookupValue.lookup_type == type_upper).delete()
    
    for item in request:
        v = LookupValue(
            lookup_type=type_upper,
            value=item.value,
            label=item.label,
            display_order=item.display_order,
            is_active=item.is_active,
            is_terminal=item.is_terminal,
            metadata_=item.metadata
        )
        db.add(v)
        
    db.commit()
    
    return api_get_lookups(lookup_type, db, token)

@router.get("/settings")
def api_get_settings(
    db: Session = Depends(get_db),
    token: str = Depends(verify_api_token)
):
    """Retrieve all hub settings."""
    values = db.query(HubSetting).all()
    return {
        "ok": True,
        "settings": {v.setting_key: v.setting_value for v in values}
    }

@router.patch("/settings")
def api_update_settings(
    request: SettingUpdateSchema,
    db: Session = Depends(get_db),
    token: str = Depends(verify_api_token)
):
    """Update a specific setting."""
    setting = db.query(HubSetting).filter(HubSetting.setting_key == request.setting_key).first()
    if not setting:
        setting = HubSetting(setting_key=request.setting_key, setting_value=request.setting_value)
        db.add(setting)
    else:
        setting.setting_value = request.setting_value
        
    db.commit()
    db.refresh(setting)
    
    return {"ok": True, "setting": {setting.setting_key: setting.setting_value}}
