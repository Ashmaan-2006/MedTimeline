from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from medgraph_api.models.patient import Patient
from medgraph_api.schemas.patient import PatientCreate, PatientUpdate


class PatientRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def list(self, skip: int = 0, limit: int = 100) -> list[Patient]:
        statement = select(Patient).offset(skip).limit(limit).order_by(Patient.created_at.desc())
        return list(self.db.scalars(statement).all())

    def get(self, patient_id: UUID) -> Patient | None:
        return self.db.get(Patient, patient_id)

    def get_by_medical_record_number(self, medical_record_number: str) -> Patient | None:
        statement = select(Patient).where(Patient.medical_record_number == medical_record_number)
        return self.db.scalar(statement)

    def create(self, payload: PatientCreate) -> Patient:
        patient = Patient(**payload.model_dump())
        self.db.add(patient)
        self.db.commit()
        self.db.refresh(patient)
        return patient

    def update(self, patient: Patient, payload: PatientUpdate) -> Patient:
        for field, value in payload.model_dump(exclude_unset=True).items():
            setattr(patient, field, value)

        self.db.add(patient)
        self.db.commit()
        self.db.refresh(patient)
        return patient

    def delete(self, patient: Patient) -> None:
        self.db.delete(patient)
        self.db.commit()

