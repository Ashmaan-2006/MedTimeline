from collections.abc import Generator

from fastapi import Depends
from sqlalchemy.orm import Session

from medgraph_api.crud.patients import PatientRepository
from medgraph_api.db.session import get_db


def get_patient_repository(db: Session = Depends(get_db)) -> Generator[PatientRepository, None, None]:
    yield PatientRepository(db)

