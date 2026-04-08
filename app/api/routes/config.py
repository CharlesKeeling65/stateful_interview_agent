from fastapi import APIRouter

from app.schemas.config import ConfigSnapshotResponse, EnvEntriesUpdate, OpencodeMindflowUpdate
from app.services.config_service import get_config_snapshot, set_mindflow_options, update_env_entries

router = APIRouter(prefix="/config", tags=["config"])


@router.get("", response_model=ConfigSnapshotResponse)
def get_config_snapshot_route():
    return get_config_snapshot()


@router.patch("/opencode-mindflow", response_model=ConfigSnapshotResponse)
def update_opencode_mindflow_route(payload: OpencodeMindflowUpdate):
    set_mindflow_options(base_url=payload.base_url, api_key=payload.api_key)
    return get_config_snapshot()


@router.patch("/env", response_model=ConfigSnapshotResponse)
def update_env_route(payload: EnvEntriesUpdate):
    update_env_entries([entry.model_dump() for entry in payload.entries])
    return get_config_snapshot()
