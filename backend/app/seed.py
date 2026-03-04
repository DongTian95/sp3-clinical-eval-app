from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from .db import Base, engine
from .models import Case, CaseImage, ModelOutput

def init_db() -> None:
    Base.metadata.create_all(bind=engine)

def seed_if_empty(db: Session) -> None:
    has_any = db.scalar(select(Case.id).limit(1)) is not None
    if has_any:
        return

    cases = [
        Case(
            title="CT Chest: Possible pulmonary embolism",
            clinical_prompt=(
                "62-year-old male with acute pleuritic chest pain and elevated D-dimer. "
                "CTPA performed. Please draft a concise radiology report with impression."
            ),
            images=[
                CaseImage(image_path="images/case1_ct_chest.png", caption="Synthetic CTPA slice (placeholder)"),
            ],
            outputs=[
                ModelOutput(
                    model_name="MockModel-A",
                    output_text=(
                        "FINDINGS:\n"
                        "- No central pulmonary embolus is identified.\n"
                        "- Mild dependent atelectasis at the lung bases.\n"
                        "- No pleural effusion.\n\n"
                        "IMPRESSION:\n"
                        "1. No evidence of pulmonary embolism.\n"
                        "2. Mild bibasilar atelectasis."
                    ),
                ),
                ModelOutput(
                    model_name="MockModel-B",
                    output_text=(
                        "FINDINGS: There is a filling defect in the RIGHT lower lobe segmental pulmonary artery "
                        "compatible with pulmonary embolism. No right heart strain. Small RIGHT pleural effusion.\n\n"
                        "IMPRESSION: Segmental PE in the right lower lobe. Recommend anticoagulation."
                    ),
                ),
            ],
        ),
        Case(
            title="CT Head: Rule out acute hemorrhage",
            clinical_prompt=(
                "74-year-old female with sudden onset left-sided weakness. Non-contrast CT head. "
                "Draft the report and highlight any urgent findings."
            ),
            images=[
                CaseImage(image_path="images/case2_ct_head.png", caption="Synthetic CT head slice (placeholder)"),
            ],
            outputs=[
                ModelOutput(
                    model_name="MockModel-A",
                    output_text=(
                        "FINDINGS:\n"
                        "No acute intracranial hemorrhage. Gray-white differentiation is preserved. "
                        "No midline shift or hydrocephalus.\n\n"
                        "IMPRESSION:\n"
                        "No acute intracranial abnormality on non-contrast CT."
                    ),
                ),
                ModelOutput(
                    model_name="MockModel-B",
                    output_text=(
                        "FINDINGS:\n"
                        "Hyperdense focus in the RIGHT basal ganglia may represent a small acute hemorrhage. "
                        "No significant mass effect.\n\n"
                        "IMPRESSION:\n"
                        "Possible small right basal ganglia hemorrhage. Recommend clinical correlation and follow-up imaging."
                    ),
                ),
            ],
        ),
        Case(
            title="MRI Knee: Meniscal tear assessment",
            clinical_prompt=(
                "29-year-old athlete with twisting injury and medial joint line pain. MRI knee performed. "
                "Provide a structured report with findings and impression."
            ),
            images=[
                CaseImage(image_path="images/case3_mri_knee.png", caption="Synthetic MRI knee slice (placeholder)"),
            ],
            outputs=[
                ModelOutput(
                    model_name="MockModel-A",
                    output_text=(
                        "FINDINGS:\n"
                        "- Medial meniscus: linear increased signal extending to the inferior articular surface "
                        "of the posterior horn, consistent with a tear.\n"
                        "- ACL/PCL intact.\n"
                        "- No full-thickness chondral defect.\n\n"
                        "IMPRESSION:\n"
                        "1. Tear of the posterior horn of the medial meniscus.\n"
                        "2. No cruciate ligament tear."
                    ),
                ),
                ModelOutput(
                    model_name="MockModel-B",
                    output_text=(
                        "FINDINGS:\n"
                        "The lateral meniscus is torn with displaced bucket-handle fragment. ACL appears disrupted.\n\n"
                        "IMPRESSION:\n"
                        "Bucket-handle tear of the lateral meniscus and ACL rupture."
                    ),
                ),
            ],
        ),
    ]

    db.add_all(cases)
    db.commit()

def init_and_seed() -> None:
    init_db()
    from .db import SessionLocal
    db = SessionLocal()
    try:
        seed_if_empty(db)
    finally:
        db.close()

if __name__ == "__main__":
    init_and_seed()
