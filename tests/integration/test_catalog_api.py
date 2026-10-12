import uuid

from sqlalchemy.orm import Session

from app.domain.enums import AppointmentType
from tests.factories import USER_A, auth_headers, make_center, make_physician

BASE = "/api/v1/catalog"


def test_catalog_endpoints_require_token(client) -> None:
    response = client.get(f"{BASE}/medical-centers")
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "unauthorized"


def test_lists_medical_centers_by_name(client, session: Session, settings) -> None:
    make_center(session, "Zeta")
    make_center(session, "Alfa")
    session.commit()

    response = client.get(f"{BASE}/medical-centers", headers=auth_headers(USER_A))

    assert response.status_code == 200
    assert [c["name"] for c in response.json()] == ["Alfa", "Zeta"]
    assert set(response.json()[0]) == {"medicalCenterId", "name", "location"}


def test_filters_physicians_by_specialty_and_center(client, session: Session, settings) -> None:
    norte = make_center(session, "Norte")
    sur = make_center(session, "Sur")
    make_physician(session, norte, AppointmentType.GENERAL)
    make_physician(session, norte, AppointmentType.PSICOLOGIA, secondary=sur)
    session.commit()

    by_specialty = client.get(
        f"{BASE}/physicians",
        params={"specialty": "PSICOLOGIA"},
        headers=auth_headers(USER_A),
    ).json()
    by_center = client.get(
        f"{BASE}/physicians",
        params={"medical_center_id": str(sur.medical_center_id)},
        headers=auth_headers(USER_A),
    ).json()

    assert [p["specialty"] for p in by_specialty] == ["PSICOLOGIA"]
    assert len(by_center) == 1
    assert by_center[0]["secondaryMedicalCenterId"] == str(sur.medical_center_id)


def test_lists_appointment_types(client, settings) -> None:
    response = client.get(f"{BASE}/appointment-types", headers=auth_headers(USER_A))
    assert response.json() == ["GENERAL", "ODONTOLOGIA", "PSICOLOGIA"]


def test_invalid_specialty_is_rejected(client, settings) -> None:
    response = client.get(
        f"{BASE}/physicians",
        params={"specialty": "CARDIOLOGIA"},
        headers=auth_headers(USER_A),
    )
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "validation_error"


def test_unknown_medical_center_filter_returns_empty_list(client, settings) -> None:
    response = client.get(
        f"{BASE}/physicians",
        params={"medical_center_id": str(uuid.uuid4())},
        headers=auth_headers(USER_A),
    )
    assert response.status_code == 200
    assert response.json() == []
