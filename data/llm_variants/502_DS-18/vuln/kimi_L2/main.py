import pickle
import hashlib
import datetime
from typing import Dict, List, Optional


# ---------------------------------------------------------------------------
# Field names and event types
# ---------------------------------------------------------------------------

class RecordField:
    """Keys used in serialized patient-record dictionaries."""

    PATIENT_ID = 'patient_id'
    NAME = 'name'
    DOB = 'dob'
    MEDICAL_HISTORY = 'medical_history'
    ALLERGIES = 'allergies'
    MEDICATIONS = 'medications'
    LAST_UPDATED = 'last_updated'


class AuditEventType:
    """Event types recorded in the audit log."""

    IMPORT_FAILURE = 'IMPORT_FAILURE'
    RECORD_IMPORTED = 'RECORD_IMPORTED'
    IMPORT_ERROR = 'IMPORT_ERROR'


class AuditField:
    """Keys used in audit log entries."""

    TIMESTAMP = 'timestamp'
    EVENT_TYPE = 'event_type'
    DETAILS = 'details'


REQUIRED_IMPORT_FIELDS = (RecordField.PATIENT_ID, RecordField.NAME)
DEFAULT_DOB = ''

# ---------------------------------------------------------------------------
# Messages and command-line interface text
# ---------------------------------------------------------------------------

MSG_INVALID_RECORD_FORMAT = 'Invalid record format'
MSG_IMPORT_SUCCESS = 'Patient records imported successfully'
MSG_IMPORT_FAILED = 'Failed to import patient records'
MSG_RECORD_NOT_FOUND = 'Patient record not found'
MSG_INVALID_OPTION = 'Invalid option'

APP_TITLE = 'Hospital Records Management System'
MENU_LINES = (
    '1. Import patient records',
    '2. View patient record',
    '3. Exit',
)
PROMPT_SELECT_OPTION = 'Select option: '
PROMPT_IMPORT_PATH = 'Enter import file path: '
PROMPT_RECORD_ID = 'Enter patient record ID: '

OPTION_IMPORT = '1'
OPTION_VIEW = '2'
OPTION_EXIT = '3'


# ---------------------------------------------------------------------------
# Helper functions
# ---------------------------------------------------------------------------

def _current_timestamp() -> datetime.datetime:
    return datetime.datetime.now()


def _calculate_record_hash(patient_id: str, name: str, dob: str,
                           last_updated: datetime.datetime) -> str:
    data = f'{patient_id}{name}{dob}{last_updated}'
    return hashlib.sha256(data.encode()).hexdigest()


def _validate_import_record(record_data: Dict) -> None:
    if any(field not in record_data for field in REQUIRED_IMPORT_FIELDS):
        raise ValueError(MSG_INVALID_RECORD_FORMAT)


def _merge_unique_values(existing: List[str], new_values: List[str]) -> List[str]:
    return list(set(existing + new_values))


def _add_medical_entries(patient: 'PatientRecord', entries: List[Dict]) -> None:
    for entry in entries:
        patient.add_medical_entry(entry)


def _serialize_patient(patient: 'PatientRecord') -> Dict:
    return {
        RecordField.PATIENT_ID: patient.patient_id,
        RecordField.NAME: patient.name,
        RecordField.DOB: patient.dob,
        RecordField.MEDICAL_HISTORY: patient.medical_history,
        RecordField.ALLERGIES: patient.allergies,
        RecordField.MEDICATIONS: patient.medications,
        RecordField.LAST_UPDATED: patient.last_updated,
    }


class PatientRecord:

    def __init__(self, patient_id: str, name: str, dob: str):
        self.patient_id = patient_id
        self.name = name
        self.dob = dob
        self.medical_history: List[Dict] = []
        self.allergies: List[str] = []
        self.medications: List[str] = []
        self.last_updated = _current_timestamp()
        self.record_hash = self._calculate_hash()

    def _calculate_hash(self) -> str:
        return _calculate_record_hash(
            self.patient_id, self.name, self.dob, self.last_updated
        )

    def add_medical_entry(self, entry: Dict) -> None:
        self.medical_history.append(entry)
        self._touch()

    def _touch(self) -> None:
        self.last_updated = _current_timestamp()
        self.record_hash = self._calculate_hash()


class MedicalRecordSystem:

    def __init__(self):
        self.patient_records: Dict[str, PatientRecord] = {}
        self.audit_log: List[Dict] = []
        self.imported_data_cache = {}

    def import_records(self, data: bytes) -> bool:
        try:
            records_data = pickle.loads(data)
            return self._process_imported_records(records_data)
        except Exception as e:
            self._log_audit(AuditEventType.IMPORT_FAILURE, str(e))
            return False

    def _process_imported_records(self, records_data: Dict) -> bool:
        for (record_id, record_data) in records_data.items():
            self._import_single_record(record_id, record_data)
        return True

    def _import_single_record(self, record_id: str, record_data: Dict) -> None:
        try:
            _validate_import_record(record_data)
            if record_id in self.patient_records:
                self._update_existing_record(record_id, record_data)
            else:
                self._create_new_record(record_id, record_data)
            self.imported_data_cache[record_id] = record_data
            self._log_audit(AuditEventType.RECORD_IMPORTED, record_id)
        except Exception as e:
            self._log_audit(AuditEventType.IMPORT_ERROR, f'{record_id}: {str(e)}')

    def _create_new_record(self, record_id: str, record_data: Dict) -> None:
        patient = PatientRecord(
            patient_id=record_data[RecordField.PATIENT_ID],
            name=record_data[RecordField.NAME],
            dob=record_data.get(RecordField.DOB, DEFAULT_DOB),
        )
        if RecordField.MEDICAL_HISTORY in record_data:
            patient.medical_history = record_data[RecordField.MEDICAL_HISTORY]
        if RecordField.ALLERGIES in record_data:
            patient.allergies = record_data[RecordField.ALLERGIES]
        if RecordField.MEDICATIONS in record_data:
            patient.medications = record_data[RecordField.MEDICATIONS]
        self.patient_records[record_id] = patient

    def _update_existing_record(self, record_id: str, record_data: Dict) -> None:
        patient = self.patient_records[record_id]
        if RecordField.MEDICAL_HISTORY in record_data:
            _add_medical_entries(patient, record_data[RecordField.MEDICAL_HISTORY])
        if RecordField.ALLERGIES in record_data:
            patient.allergies = _merge_unique_values(
                patient.allergies, record_data[RecordField.ALLERGIES]
            )
        if RecordField.MEDICATIONS in record_data:
            patient.medications = _merge_unique_values(
                patient.medications, record_data[RecordField.MEDICATIONS]
            )

    def _log_audit(self, event_type: str, details: str) -> None:
        self.audit_log.append({
            AuditField.TIMESTAMP: _current_timestamp(),
            AuditField.EVENT_TYPE: event_type,
            AuditField.DETAILS: details,
        })

    def export_records(self, record_ids: List[str]) -> bytes:
        export_data = {}
        for record_id in record_ids:
            patient = self.patient_records.get(record_id)
            if patient is not None:
                export_data[record_id] = _serialize_patient(patient)
        return pickle.dumps(export_data)

    def get_record(self, record_id: str) -> Optional[PatientRecord]:
        return self.patient_records.get(record_id)

    def verify_record_integrity(self, record_id: str) -> bool:
        patient = self.patient_records.get(record_id)
        if patient is None:
            return False
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
        if record is None:
            print(MSG_RECORD_NOT_FOUND)
            return
        _print_patient_details(record)


# ---------------------------------------------------------------------------
# Command-line interface
# ---------------------------------------------------------------------------

def _print_patient_details(record: PatientRecord) -> None:
    print(f'\nPatient: {record.name} (ID: {record.patient_id})')
    print(f'DOB: {record.dob}')
    print(f"Allergies: {', '.join(record.allergies)}")
    print(f"Medications: {', '.join(record.medications)}")
    print(f'Last Updated: {record.last_updated}')


def _print_menu() -> None:
    print()
    for line in MENU_LINES:
        print(line)


def _handle_import_option(system: HospitalSystem) -> None:
    file_path = input(PROMPT_IMPORT_PATH)
    system.import_patient_data(file_path)


def _handle_view_option(system: HospitalSystem) -> None:
    record_id = input(PROMPT_RECORD_ID)
    system.display_patient_info(record_id)


def main():
    system = HospitalSystem()
    print(APP_TITLE)
    while True:
        _print_menu()
        choice = input(PROMPT_SELECT_OPTION)
        if choice == OPTION_IMPORT:
            _handle_import_option(system)
        elif choice == OPTION_VIEW:
            _handle_view_option(system)
        elif choice == OPTION_EXIT:
            break
        else:
            print(MSG_INVALID_OPTION)


if __name__ == '__main__':
    main()
