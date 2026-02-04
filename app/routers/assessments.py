import io
import json
from typing import List

import pandas as pd
import pdfplumber
from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from sqlalchemy.orm import Session

from app.core.security import decrypt_sensitive, encrypt_sensitive
from app.db.session import get_db
from app import models, schemas
from app.routers.auth import get_current_user
from app.services.assessment import analyze_financials
from app.services.llm_client import enhance_narrative_with_llm


router = APIRouter(prefix="/assessments", tags=["assessments"])

SUPPORTED_MIME_TYPES = {
    "text/csv",
    "application/vnd.ms-excel",
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    "application/pdf",
}


def _load_dataframe_from_upload(upload: UploadFile) -> pd.DataFrame:
    if upload.content_type not in SUPPORTED_MIME_TYPES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unsupported file type: {upload.content_type}",
        )

    content = upload.file.read()

    if upload.content_type == "text/csv":
        return pd.read_csv(io.BytesIO(content))
    if upload.content_type in {
        "application/vnd.ms-excel",
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    }:
        return pd.read_excel(io.BytesIO(content))
    if upload.content_type == "application/pdf":
        # Basic PDF table extraction; assumes text-based PDF exports
        tables: List[pd.DataFrame] = []
        with pdfplumber.open(io.BytesIO(content)) as pdf:
            for page in pdf.pages:
                table = page.extract_table()
                if table:
                    df_page = pd.DataFrame(table[1:], columns=table[0])
                    tables.append(df_page)
        if not tables:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Could not extract tabular data from PDF. Please upload CSV/XLSX exported from your system.",
            )
        return pd.concat(tables, ignore_index=True)

    raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Unsupported file format")


@router.post(
    "",
    response_model=schemas.AssessmentRead,
    status_code=status.HTTP_201_CREATED,
)
async def create_assessment(
    meta: str = Form(..., description="JSON string with business_name, industry, locale"),
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    """
    Upload a financial data file and create a new assessment.
    """
    try:
        payload = json.loads(meta)
        meta_in = schemas.AssessmentCreate(**payload)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid meta payload")

    df = _load_dataframe_from_upload(file)
    result, _ = analyze_financials(df, industry=meta_in.industry)
    result = await enhance_narrative_with_llm(result)

    raw_bytes = file.file.read()
    if not raw_bytes:
        # if file was already read for parsing, use that buffer
        file.file.seek(0)
        raw_bytes = file.file.read()

    encrypted = encrypt_sensitive(raw_bytes)

    summary_json = result.model_dump_json()

    assessment = models.Assessment(
        owner_id=current_user.id,
        business_name=meta_in.business_name,
        industry=meta_in.industry,
        locale=meta_in.locale,
        file_name=file.filename or "upload",
        file_mime_type=file.content_type or "application/octet-stream",
        file_data_encrypted=encrypted,
        summary_json=summary_json,
    )
    db.add(assessment)
    db.commit()
    db.refresh(assessment)

    return schemas.AssessmentRead(
        id=assessment.id,
        business_name=assessment.business_name,
        industry=assessment.industry,
        locale=assessment.locale,
        created_at=assessment.created_at,
        summary=result,
    )


@router.get("", response_model=list[schemas.AssessmentRead])
def list_assessments(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    records = (
        db.query(models.Assessment)
        .filter(models.Assessment.owner_id == current_user.id)
        .order_by(models.Assessment.created_at.desc())
        .all()
    )

    result: list[schemas.AssessmentRead] = []
    for a in records:
        summary = None
        if a.summary_json:
            try:
                summary = schemas.AssessmentResult.model_validate_json(a.summary_json)
            except Exception:
                summary = None
        result.append(
            schemas.AssessmentRead(
                id=a.id,
                business_name=a.business_name,
                industry=a.industry,
                locale=a.locale,
                created_at=a.created_at,
                summary=summary,
            )
        )
    return result

