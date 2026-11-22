import json
import hashlib
import datetime
from typing import Any, Dict, List, Optional

# --- Constants --------------------------------------------------------------

ENCODING = 'utf-8'

FIELD_PATIENT_ID = 'patient_id'
FIELD_NAME = 'name'
FIELD_DOB = 'dob'
FIELD_MEDICAL_HISTORY = 'medical_history'
FIELD_ALLERGIES = 'allergies'
FIELD_MEDICATIONS = 'medications'
FIELD_LAST_UPDATED = 'last_updated'

REQUIRED_RECORD_FIELDS = (FIELD_PATIENT_ID, FIELD_NAME)

EVENT_IMPORT_FAILURE = 'IMPORT_FAILURE'
EVENT_RECORD_IMPORTED = 'RECORD_IMPORTED'
EVENT_IMPORT_ERROR = 'IMPORT_ERROR'

MSG_INVALID_RECORD_FORMAT = 'Invalid record format'
MSG_IMPORT_SUCCESS = 'Patient records imported successfully'
MSG_IMPORT_FAILED = 'Failed to import patient records'
MSG_RECORD_NOT_FOUND = 'Patient record not found'

MENU_IMPORT = '1'
MENU_VIEW = '2'
MENU_EXIT = '3'


# --- Helpers ----------------------------------------------------------------

def _now() -> datetime.datetime:
    return datetime.datetime.now()


def _list_field(record_data: Dict, key: str) -> Optional[list]:
    """Return record_data[key] if present and a list, otherwise None."""
    value = record_data.get(key)
    return value if isinstance(value, list) else None


def _is_valid_record(record_data: Any) -> bool:
    return isinstance(record_data, dict) and all(
        field in record_data for field in REQUIRED_RECORD_FIELDS
    )


# --- Domain model -----------------------------------------------------------

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
        return hashlib.sha256(data.encode()).hexdigest()

    def add_medical_entry(self, entry: Dict) -> None:
        self.medical_history.append(entry)
        self.last_updated = _now()
        self.record_hash = self._calculate_hash()


class MedicalRecordSystem:

    def __init__(self):
        self.patient_records: Dict[str, PatientRecord] = {}
        self.audit_log: List[Dict] = []
        self.imported_data_cache = {}

    # -- Import --------------------------------------------------------------

    def import_records(self, data: bytes) -> bool:
        try:
            records_data = json.loads(data.decode(ENCODING))
            return self._process_imported_records(records_data)
        except Exception as e:
            self._log_audit(EVENT_IMPORT_FAILURE, str(e))
            return False

    def _process_imported_records(self, records_data: Dict) -> bool:
        for (record_id, record_data) in records_data.items():
            try:
                self._import_single_record(record_id, record_data)
                self._log_audit(EVENT_RECORD_IMPORTED, record_id)
            except Exception as e:
                self._log_audit(EVENT_IMPORT_ERROR, f'{record_id}: {str(e)}')
        return True

    def _import_single_record(self, record_id: str, record_data: Any) -> None:
        if not _is_valid_record(record_data):
            raise ValueError(MSG_INVALID_RECORD_FORMAT)
        if record_id in self.patient_records:
            self._update_existing_record(record_id, record_data)
        else:
            self._create_new_record(record_id, record_data)
        self.imported_data_cache[record_id] = record_data

    def _create_new_record(self, record_id: str, record_data: Dict) -> None:
        patient = PatientRecord(
            patient_id=record_data[FIELD_PATIENT_ID],
            name=record_data[FIELD_NAME],
            dob=record_data.get(FIELD_DOB, ''),
        )
        history = _list_field(record_data, FIELD_MEDICAL_HISTORY)
        if history is not None:
            patient.medical_history = history
        allergies = _list_field(record_data, FIELD_ALLERGIES)
        if allergies is not None:
            patient.allergies = allergies
        medications = _list_field(record_data, FIELD_MEDICATIONS)
        if medications is not None:
            patient.medications = medications
        self.patient_records[record_id] = patient

    def _update_existing_record(self, record_id: str, record_data: Dict) -> None:
        patient = self.patient_records[record_id]
        history = _list_field(record_data, FIELD_MEDICAL_HISTORY)
        if history is not None:
            for entry in history:
                if isinstance(entry, dict):
                    patient.add_medical_entry(entry)
        allergies = _list_field(record_data, FIELD_ALLERGIES)
        if allergies is not None:
            patient.allergies = list(set(patient.allergies + allergies))
        medications = _list_field(record_data, FIELD_MEDICATIONS)
        if medications is not None:
            patient.medications = list(set(patient.medications + medications))

    # -- Audit ---------------------------------------------------------------

    def _log_audit(self, event_type: str, details: str) -> None:
        self.audit_log.append({
            'timestamp': _now(),
            'event_type': event_type,
            'details': details,
        })

    # -- Export --------------------------------------------------------------

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

    def export_records(self, record_ids: List[str]) -> bytes:
        export_data = {}
        for record_id in record_ids:
            if record_id in self.patient_records:
                export_data[record_id] = self._serialize_patient(
                    self.patient_records[record_id]
                )
        return json.dumps(export_data).encode(ENCODING)

    # -- Queries -------------------------------------------------------------

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
            print(f'\nPatient: {record.name} (ID: {record.patient_id})')
            print(f'DOB: {record.dob}')
            print(f"Allergies: {', '.join(record.allergies)}")
            print(f"Medications: {', '.join(record.medications)}")
            print(f'Last Updated: {record.last_updated}')
        else:
            print(MSG_RECORD_NOT_FOUND)


# --- CLI --------------------------------------------------------------------

def _print_menu() -> None:
    print('\n1. Import patient records')
    print('2. View patient record')
    print('3. Exit')


def main():
    system = HospitalSystem()
    print('Hospital Records Management System')
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
            print('Invalid option')


if __name__ == '__main__':
    main()
