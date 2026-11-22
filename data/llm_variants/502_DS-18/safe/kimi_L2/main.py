"""Hospital Records Management System.

Refactored for a larger production codebase: named constants for audit event
types, record field keys and user-facing messages, plus small helper
functions/methods for shared operations. All public names, signatures and the
CLI remain unchanged.
"""

import json
import hashlib
import datetime
from typing import Dict, List, Optional

# ---------------------------------------------------------------------------
# Configuration constants
# ---------------------------------------------------------------------------

ENCODING = 'utf-8'

# Audit event types.
EVENT_IMPORT_FAILURE = 'IMPORT_FAILURE'
EVENT_RECORD_IMPORTED = 'RECORD_IMPORTED'
EVENT_IMPORT_ERROR = 'IMPORT_ERROR'

# Patient record field keys.
FIELD_PATIENT_ID = 'patient_id'
FIELD_NAME = 'name'
FIELD_DOB = 'dob'
FIELD_MEDICAL_HISTORY = 'medical_history'
FIELD_ALLERGIES = 'allergies'
FIELD_MEDICATIONS = 'medications'
FIELD_LAST_UPDATED = 'last_updated'

REQUIRED_IMPORT_FIELDS = (FIELD_PATIENT_ID, FIELD_NAME)
LIST_IMPORT_FIELDS = (FIELD_MEDICAL_HISTORY, FIELD_ALLERGIES, FIELD_MEDICATIONS)

# User-facing messages.
MSG_INVALID_RECORD_FORMAT = 'Invalid record format'
MSG_IMPORT_SUCCESS = 'Patient records imported successfully'
MSG_IMPORT_FAILED = 'Failed to import patient records'
MSG_RECORD_NOT_FOUND = 'Patient record not found'
MSG_INVALID_OPTION = 'Invalid option'

# CLI text.
APP_TITLE = 'Hospital Records Management System'
MENU_LINES = (
    '\n1. Import patient records',
    '2. View patient record',
    '3. Exit',
)
PROMPT_SELECT_OPTION = 'Select option: '
PROMPT_IMPORT_FILE_PATH = 'Enter import file path: '
PROMPT_RECORD_ID = 'Enter patient record ID: '
CHOICE_IMPORT = '1'
CHOICE_VIEW = '2'
CHOICE_EXIT = '3'


# ---------------------------------------------------------------------------
# Small shared helpers
# ---------------------------------------------------------------------------

def _now() -> datetime.datetime:
    """Return the current local datetime."""
    return datetime.datetime.now()


def _sha256_hexdigest(text: str) -> str:
    """Return the SHA-256 hex digest of ``text``."""
    return hashlib.sha256(text.encode(ENCODING)).hexdigest()


class PatientRecord:

    def __init__(self, patient_id: str, name: str, dob: str):
        self.patient_id = patient_id
        self.name = name
        self.dob = dob
        self.medical_history: List[Dict] = []
        self.allergies: List[str] = []
        self.medications: List[str] = []
        self.last_updated = _now()
        self.record_hash = self._calculate_hash()

    def _calculate_hash(self) -> str:
        data = f'{self.patient_id}{self.name}{self.dob}{self.last_updated}'
        return _sha256_hexdigest(data)

    def _refresh_integrity(self) -> None:
        """Update the modification timestamp and recompute the record hash."""
        self.last_updated = _now()
        self.record_hash = self._calculate_hash()

    def add_medical_entry(self, entry: Dict) -> None:
        self.medical_history.append(entry)
        self._refresh_integrity()


class MedicalRecordSystem:

    def __init__(self):
        self.patient_records: Dict[str, PatientRecord] = {}
        self.audit_log: List[Dict] = []
        self.imported_data_cache = {}

    # -- Import ---------------------------------------------------------

    def import_records(self, data: bytes) -> bool:
        try:
            records_data = json.loads(data.decode(ENCODING))
            return self._process_imported_records(records_data)
        except Exception as e:
            self._log_audit(EVENT_IMPORT_FAILURE, str(e))
            return False

    def _process_imported_records(self, records_data: Dict) -> bool:
        for record_id, record_data in records_data.items():
            try:
                self._import_single_record(record_id, record_data)
            except Exception as e:
                self._log_audit(EVENT_IMPORT_ERROR, f'{record_id}: {str(e)}')
        return True

    def _import_single_record(self, record_id: str, record_data: Dict) -> None:
        self._validate_import_record(record_data)
        if record_id in self.patient_records:
            self._update_existing_record(record_id, record_data)
        else:
            self._create_new_record(record_id, record_data)
        self.imported_data_cache[record_id] = record_data
        self._log_audit(EVENT_RECORD_IMPORTED, record_id)

    @staticmethod
    def _validate_import_record(record_data: Dict) -> None:
        if not isinstance(record_data, dict) or any(
            field not in record_data for field in REQUIRED_IMPORT_FIELDS
        ):
            raise ValueError(MSG_INVALID_RECORD_FORMAT)

    def _create_new_record(self, record_id: str, record_data: Dict) -> None:
        patient = PatientRecord(
            patient_id=record_data[FIELD_PATIENT_ID],
            name=record_data[FIELD_NAME],
            dob=record_data.get(FIELD_DOB, ''),
        )
        self._apply_list_fields(patient, record_data)
        self.patient_records[record_id] = patient

    def _update_existing_record(self, record_id: str, record_data: Dict) -> None:
        patient = self.patient_records[record_id]
        self._merge_medical_history(patient, record_data)
        self._merge_unique_list_field(patient, record_data, FIELD_ALLERGIES)
        self._merge_unique_list_field(patient, record_data, FIELD_MEDICATIONS)

    # -- Import helpers ---------------------------------------------------

    @staticmethod
    def _list_field_value(record_data: Dict, field: str) -> Optional[List]:
        """Return the value of ``field`` only when it is a list, else ``None``."""
        value = record_data.get(field)
        return value if isinstance(value, list) else None

    def _apply_list_fields(self, patient: PatientRecord, record_data: Dict) -> None:
        for field in LIST_IMPORT_FIELDS:
            value = self._list_field_value(record_data, field)
            if value is not None:
                setattr(patient, field, value)

    def _merge_medical_history(self, patient: PatientRecord, record_data: Dict) -> None:
        entries = self._list_field_value(record_data, FIELD_MEDICAL_HISTORY)
        if entries is None:
            return
        for entry in entries:
            if isinstance(entry, dict):
                patient.add_medical_entry(entry)

    def _merge_unique_list_field(self, patient: PatientRecord, record_data: Dict, field: str) -> None:
        new_values = self._list_field_value(record_data, field)
        if new_values is None:
            return
        merged = list(set(getattr(patient, field) + new_values))
        setattr(patient, field, merged)

    # -- Audit ------------------------------------------------------------

    def _log_audit(self, event_type: str, details: str) -> None:
        self.audit_log.append({
            'timestamp': _now(),
            'event_type': event_type,
            'details': details,
        })

    # -- Export and queries -------------------------------------------------

    def export_records(self, record_ids: List[str]) -> bytes:
        export_data = {}
        for record_id in record_ids:
            if record_id in self.patient_records:
                patient = self.patient_records[record_id]
                export_data[record_id] = self._serialize_patient(patient)
        return json.dumps(export_data).encode(ENCODING)

    @staticmethod
    def _serialize_patient(patient: PatientRecord) -> Dict:
        return {
            FIELD_PATIENT_ID: patient.patient_id,
            FIELD_NAME: patient.name,
            FIELD_DOB: patient.dob,
            FIELD_MEDICAL_HISTORY: patient.medical_history,
            FIELD_ALLERGIES: patient.allergies,
            FIELD_MEDICATIONS: patient.medications,
            FIELD_LAST_UPDATED: patient.last_updated.isoformat(),
        }

    def get_record(self, record_id: str) -> Optional[PatientRecord]:
        return self.patient_records.get(record_id)

    def verify_record_integrity(self, record_id: str) -> bool:
        if record_id not in self.patient_records:
            return False
        patient = self.patient_records[record_id]
        return patient.record_hash == patient._calculate_hash()


class HospitalSystem:

    def __init__(self):
        self.record_system = MedicalRecordSystem()

    def import_patient_data(self, file_path: str) -> None:
        with open(file_path, 'rb') as f:
            data = f.read()
            if self.record_system.import_records(data):
                print(MSG_IMPORT_SUCCESS)
            else:
                print(MSG_IMPORT_FAILED)

    def display_patient_info(self, record_id: str) -> None:
        record = self.record_system.get_record(record_id)
        if record:
            self._print_patient_info(record)
        else:
            print(MSG_RECORD_NOT_FOUND)

    @staticmethod
    def _print_patient_info(record: PatientRecord) -> None:
        print(f'\nPatient: {record.name} (ID: {record.patient_id})')
        print(f'DOB: {record.dob}')
        print(f"Allergies: {', '.join(record.allergies)}")
        print(f"Medications: {', '.join(record.medications)}")
        print(f'Last Updated: {record.last_updated}')


# ---------------------------------------------------------------------------
# Command-line interface
# ---------------------------------------------------------------------------

def _print_menu() -> None:
    for line in MENU_LINES:
        print(line)


def _handle_import(system: HospitalSystem) -> None:
    file_path = input(PROMPT_IMPORT_FILE_PATH)
    system.import_patient_data(file_path)


def _handle_view(system: HospitalSystem) -> None:
    record_id = input(PROMPT_RECORD_ID)
    system.display_patient_info(record_id)


def main():
    system = HospitalSystem()
    print(APP_TITLE)
    while True:
        _print_menu()
        choice = input(PROMPT_SELECT_OPTION)
        if choice == CHOICE_IMPORT:
            _handle_import(system)
        elif choice == CHOICE_VIEW:
            _handle_view(system)
        elif choice == CHOICE_EXIT:
            break
        else:
            print(MSG_INVALID_OPTION)


if __name__ == '__main__':
    main()
