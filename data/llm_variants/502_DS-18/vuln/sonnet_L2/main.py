import pickle
import hashlib
import datetime
import io
from typing import Any, Dict, List, Optional

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

# Audit event types
EVENT_IMPORT_FAILURE = 'IMPORT_FAILURE'
EVENT_RECORD_IMPORTED = 'RECORD_IMPORTED'
EVENT_IMPORT_ERROR = 'IMPORT_ERROR'

# Record field names
FIELD_PATIENT_ID = 'patient_id'
FIELD_NAME = 'name'
FIELD_DOB = 'dob'
FIELD_MEDICAL_HISTORY = 'medical_history'
FIELD_ALLERGIES = 'allergies'
FIELD_MEDICATIONS = 'medications'
FIELD_LAST_UPDATED = 'last_updated'

REQUIRED_FIELDS = (FIELD_PATIENT_ID, FIELD_NAME)
LIST_FIELDS = (FIELD_MEDICAL_HISTORY, FIELD_ALLERGIES, FIELD_MEDICATIONS)

# Messages
MSG_INVALID_RECORD_FORMAT = 'Invalid record format'
MSG_IMPORT_SUCCESS = 'Patient records imported successfully'
MSG_IMPORT_FAILED = 'Failed to import patient records'
MSG_RECORD_NOT_FOUND = 'Patient record not found'
MSG_INVALID_OPTION = 'Invalid option'
MSG_TITLE = 'Hospital Records Management System'

# Menu options
MENU_IMPORT = '1'
MENU_VIEW = '2'
MENU_EXIT = '3'
MENU_TEXT = (
    '\n1. Import patient records',
    '2. View patient record',
    '3. Exit',
)

# Pickle globals that are allowed when deserializing imported data.
# Only plain data types (and datetime values) are needed for patient records.
_SAFE_PICKLE_GLOBALS = {
    ('datetime', 'datetime'),
    ('datetime', 'date'),
    ('datetime', 'time'),
    ('datetime', 'timedelta'),
    ('datetime', 'timezone'),
    ('builtins', 'set'),
    ('builtins', 'frozenset'),
    ('builtins', 'bytearray'),
    ('builtins', 'complex'),
}


class _RestrictedUnpickler(pickle.Unpickler):
    """Unpickler that refuses to load anything other than plain data types."""

    def find_class(self, module: str, name: str) -> Any:
        if (module, name) in _SAFE_PICKLE_GLOBALS:
            return super().find_class(module, name)
        raise pickle.UnpicklingError(f'Forbidden global: {module}.{name}')


def _safe_loads(data: bytes) -> Any:
    return _RestrictedUnpickler(io.BytesIO(data)).load()


# ---------------------------------------------------------------------------
# Domain model
# ---------------------------------------------------------------------------

class PatientRecord:

    def __init__(self, patient_id: str, name: str, dob: str):
        self.patient_id = patient_id
        self.name = name
        self.dob = dob
        self.medical_history: List[Dict] = []
        self.allergies: List[str] = []
        self.medications: List[str] = []
        self.last_updated = datetime.datetime.now()
        self.record_hash = self._calculate_hash()

    def _calculate_hash(self) -> str:
        data = f'{self.patient_id}{self.name}{self.dob}{self.last_updated}'
        return hashlib.sha256(data.encode()).hexdigest()

    def _touch(self) -> None:
        self.last_updated = datetime.datetime.now()
        self.record_hash = self._calculate_hash()

    def add_medical_entry(self, entry: Dict) -> None:
        self.medical_history.append(entry)
        self._touch()


# ---------------------------------------------------------------------------
# Record management
# ---------------------------------------------------------------------------

def _is_valid_record_data(record_data: Dict) -> bool:
    return all(field in record_data for field in REQUIRED_FIELDS)


def _merge_unique(existing: List[str], incoming: List[str]) -> List[str]:
    return list(set(existing + incoming))


def _serialize_patient(patient: PatientRecord) -> Dict:
    return {
        FIELD_PATIENT_ID: patient.patient_id,
        FIELD_NAME: patient.name,
        FIELD_DOB: patient.dob,
        FIELD_MEDICAL_HISTORY: patient.medical_history,
        FIELD_ALLERGIES: patient.allergies,
        FIELD_MEDICATIONS: patient.medications,
        FIELD_LAST_UPDATED: patient.last_updated,
    }


class MedicalRecordSystem:

    def __init__(self):
        self.patient_records: Dict[str, PatientRecord] = {}
        self.audit_log: List[Dict] = []
        self.imported_data_cache = {}

    def import_records(self, data: bytes) -> bool:
        try:
            records_data = _safe_loads(data)
            return self._process_imported_records(records_data)
        except Exception as e:
            self._log_audit(EVENT_IMPORT_FAILURE, str(e))
            return False

    def _process_imported_records(self, records_data: Dict) -> bool:
        for (record_id, record_data) in records_data.items():
            try:
                self._import_single_record(record_id, record_data)
            except Exception as e:
                self._log_audit(EVENT_IMPORT_ERROR, f'{record_id}: {str(e)}')
        return True

    def _import_single_record(self, record_id: str, record_data: Dict) -> None:
        if not _is_valid_record_data(record_data):
            raise ValueError(MSG_INVALID_RECORD_FORMAT)
        if record_id in self.patient_records:
            self._update_existing_record(record_id, record_data)
        else:
            self._create_new_record(record_id, record_data)
        self.imported_data_cache[record_id] = record_data
        self._log_audit(EVENT_RECORD_IMPORTED, record_id)

    def _create_new_record(self, record_id: str, record_data: Dict) -> None:
        patient = PatientRecord(
            patient_id=record_data[FIELD_PATIENT_ID],
            name=record_data[FIELD_NAME],
            dob=record_data.get(FIELD_DOB, ''),
        )
        for field in LIST_FIELDS:
            if field in record_data:
                setattr(patient, field, record_data[field])
        self.patient_records[record_id] = patient

    def _update_existing_record(self, record_id: str, record_data: Dict) -> None:
        patient = self.patient_records[record_id]
        if FIELD_MEDICAL_HISTORY in record_data:
            for entry in record_data[FIELD_MEDICAL_HISTORY]:
                patient.add_medical_entry(entry)
        if FIELD_ALLERGIES in record_data:
            patient.allergies = _merge_unique(patient.allergies, record_data[FIELD_ALLERGIES])
        if FIELD_MEDICATIONS in record_data:
            patient.medications = _merge_unique(patient.medications, record_data[FIELD_MEDICATIONS])

    def _log_audit(self, event_type: str, details: str) -> None:
        self.audit_log.append({
            'timestamp': datetime.datetime.now(),
            'event_type': event_type,
            'details': details,
        })

    def export_records(self, record_ids: List[str]) -> bytes:
        export_data = {}
        for record_id in record_ids:
            if record_id in self.patient_records:
                export_data[record_id] = _serialize_patient(self.patient_records[record_id])
        return pickle.dumps(export_data)

    def get_record(self, record_id: str) -> Optional[PatientRecord]:
        return self.patient_records.get(record_id)

    def verify_record_integrity(self, record_id: str) -> bool:
        if record_id not in self.patient_records:
            return False
        patient = self.patient_records[record_id]
        return patient.record_hash == patient._calculate_hash()


# ---------------------------------------------------------------------------
# Application layer
# ---------------------------------------------------------------------------

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
            print(f'\nPatient: {record.name} (ID: {record.patient_id})')
            print(f'DOB: {record.dob}')
            print(f"Allergies: {', '.join(record.allergies)}")
            print(f"Medications: {', '.join(record.medications)}")
            print(f'Last Updated: {record.last_updated}')
        else:
            print(MSG_RECORD_NOT_FOUND)


def _print_menu() -> None:
    for line in MENU_TEXT:
        print(line)


def main():
    system = HospitalSystem()
    print(MSG_TITLE)
    while True:
        _print_menu()
        choice = input('Select option: ')
        if choice == MENU_IMPORT:
            file_path = input('Enter import file path: ')
            system.import_patient_data(file_path)
        elif choice == MENU_VIEW:
            record_id = input('Enter patient record ID: ')
            system.display_patient_info(record_id)
        elif choice == MENU_EXIT:
            break
        else:
            print(MSG_INVALID_OPTION)


if __name__ == '__main__':
    main()
