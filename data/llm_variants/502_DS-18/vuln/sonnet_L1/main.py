import pickle
import hashlib
import datetime
from typing import Dict, List, Optional

# Audit event types
EVENT_IMPORT_FAILURE = 'IMPORT_FAILURE'
EVENT_RECORD_IMPORTED = 'RECORD_IMPORTED'
EVENT_IMPORT_ERROR = 'IMPORT_ERROR'

# Fields that must be present in every imported record
REQUIRED_RECORD_FIELDS = ('patient_id', 'name')

# Optional list-valued fields copied/merged during import
LIST_FIELDS = ('allergies', 'medications')


class PatientRecord:
    """A patient's data together with an integrity hash."""

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
        """Refresh the modification timestamp and the integrity hash."""
        self.last_updated = datetime.datetime.now()
        self.record_hash = self._calculate_hash()

    def add_medical_entry(self, entry: Dict) -> None:
        self.medical_history.append(entry)
        self._touch()


class MedicalRecordSystem:
    """Stores patient records and handles import/export of them."""

    def __init__(self):
        self.patient_records: Dict[str, PatientRecord] = {}
        self.audit_log: List[Dict] = []
        self.imported_data_cache = {}

    # ---- Import ----------------------------------------------------------

    def import_records(self, data: bytes) -> bool:
        try:
            # NOTE: deserialisation format is unchanged (pickle) to preserve
            # existing behaviour.
            records_data = pickle.loads(data)
            return self._process_imported_records(records_data)
        except Exception as e:
            self._log_audit(EVENT_IMPORT_FAILURE, str(e))
            return False

    def _process_imported_records(self, records_data: Dict) -> bool:
        for record_id, record_data in records_data.items():
            try:
                self._validate_record_data(record_data)
                if record_id in self.patient_records:
                    self._update_existing_record(record_id, record_data)
                else:
                    self._create_new_record(record_id, record_data)
                self.imported_data_cache[record_id] = record_data
                self._log_audit(EVENT_RECORD_IMPORTED, record_id)
            except Exception as e:
                self._log_audit(EVENT_IMPORT_ERROR, f'{record_id}: {str(e)}')
        return True

    @staticmethod
    def _validate_record_data(record_data: Dict) -> None:
        if any(field not in record_data for field in REQUIRED_RECORD_FIELDS):
            raise ValueError('Invalid record format')

    def _create_new_record(self, record_id: str, record_data: Dict) -> None:
        patient = PatientRecord(
            patient_id=record_data['patient_id'],
            name=record_data['name'],
            dob=record_data.get('dob', ''),
        )
        if 'medical_history' in record_data:
            patient.medical_history = record_data['medical_history']
        for field in LIST_FIELDS:
            if field in record_data:
                setattr(patient, field, record_data[field])
        self.patient_records[record_id] = patient

    def _update_existing_record(self, record_id: str, record_data: Dict) -> None:
        patient = self.patient_records[record_id]
        if 'medical_history' in record_data:
            for entry in record_data['medical_history']:
                patient.add_medical_entry(entry)
        for field in LIST_FIELDS:
            if field in record_data:
                merged = list(set(getattr(patient, field) + record_data[field]))
                setattr(patient, field, merged)

    # ---- Audit -----------------------------------------------------------

    def _log_audit(self, event_type: str, details: str) -> None:
        self.audit_log.append({
            'timestamp': datetime.datetime.now(),
            'event_type': event_type,
            'details': details,
        })

    # ---- Export / query --------------------------------------------------

    @staticmethod
    def _serialize_patient(patient: PatientRecord) -> Dict:
        return {
            'patient_id': patient.patient_id,
            'name': patient.name,
            'dob': patient.dob,
            'medical_history': patient.medical_history,
            'allergies': patient.allergies,
            'medications': patient.medications,
            'last_updated': patient.last_updated,
        }

    def export_records(self, record_ids: List[str]) -> bytes:
        export_data = {
            record_id: self._serialize_patient(self.patient_records[record_id])
            for record_id in record_ids
            if record_id in self.patient_records
        }
        return pickle.dumps(export_data)

    def get_record(self, record_id: str) -> Optional[PatientRecord]:
        return self.patient_records.get(record_id)

    def verify_record_integrity(self, record_id: str) -> bool:
        patient = self.patient_records.get(record_id)
        if patient is None:
            return False
        return patient.record_hash == patient._calculate_hash()


class HospitalSystem:
    """User-facing operations on top of the record system."""

    def __init__(self):
        self.record_system = MedicalRecordSystem()

    def import_patient_data(self, file_path: str) -> None:
        with open(file_path, 'rb') as f:
            data = f.read()
            if self.record_system.import_records(data):
                print('Patient records imported successfully')
            else:
                print('Failed to import patient records')

    def display_patient_info(self, record_id: str) -> None:
        record = self.record_system.get_record(record_id)
        if record:
            print(f'\nPatient: {record.name} (ID: {record.patient_id})')
            print(f'DOB: {record.dob}')
            print(f"Allergies: {', '.join(record.allergies)}")
            print(f"Medications: {', '.join(record.medications)}")
            print(f'Last Updated: {record.last_updated}')
        else:
            print('Patient record not found')


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
        if choice == '1':
            file_path = input('Enter import file path: ')
            system.import_patient_data(file_path)
        elif choice == '2':
            record_id = input('Enter patient record ID: ')
            system.display_patient_info(record_id)
        elif choice == '3':
            break
        else:
            print('Invalid option')


if __name__ == '__main__':
    main()
