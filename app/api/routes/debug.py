from fastapi import APIRouter

from app.services.llm_test import test_llm_call

router = APIRouter(prefix="/debug", tags=["debug"])


@router.get("/llm")
def debug_llm():
    return test_llm_call()
