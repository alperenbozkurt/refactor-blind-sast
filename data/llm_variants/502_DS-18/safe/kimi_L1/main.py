"""Hospital patient records management system.

Provides classes for storing, importing, exporting and verifying patient
medical records, along with a simple command-line interface.
"""

import datetime
import hashlib
import json
from typing import Dict, List, Optional


class PatientRecord:
    """A single patient's medical record and its integrity hash."""

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

    def add_medical_entry(self, entry: Dict) -> None:
        self.medical_history.append(entry)
        self.last_updated = datetime.datetime.now()
        self.record_hash = self._calculate_hash()


class MedicalRecordSystem:
    """Stores patient records and handles import, export and auditing."""

    REQUIRED_RECORD_FIELDS = ('patient_id', 'name')
    LIST_FIELDS = ('medical_history', 'allergies', 'medications')

    def __init__(self):
        self.patient_records: Dict[str, PatientRecord] = {}
        self.audit_log: List[Dict] = []
        self.imported_data_cache: Dict[str, Dict] = {}

    def import_records(self, data: bytes) -> bool:
        try:
            records_data = json.loads(data.decode('utf-8'))
            return self._process_imported_records(records_data)
        except Exception as e:
            self._log_audit('IMPORT_FAILURE', str(e))
            return False

    def _process_imported_records(self, records_data: Dict) -> bool:
        for record_id, record_data in records_data.items():
            try:
                self._validate_record_format(record_data)
                if record_id in self.patient_records:
                    self._update_existing_record(record_id, record_data)
                else:
                    self._create_new_record(record_id, record_data)
                self.imported_data_cache[record_id] = record_data
                self._log_audit('RECORD_IMPORTED', record_id)
            except Exception as e:
                self._log_audit('IMPORT_ERROR', f'{record_id}: {e}')
        return True

    def _validate_record_format(self, record_data: Dict) -> None:
        if not isinstance(record_data, dict):
            raise ValueError('Invalid record format')
        if any(field not in record_data for field in self.REQUIRED_RECORD_FIELDS):
            raise ValueError('Invalid record format')

    def _create_new_record(self, record_id: str, record_data: Dict) -> None:
        patient = PatientRecord(
            patient_id=record_data['patient_id'],
            name=record_data['name'],
            dob=record_data.get('dob', ''),
        )
        for field in self.LIST_FIELDS:
            value = record_data.get(field)
            if isinstance(value, list):
                setattr(patient, field, value)
        self.patient_records[record_id] = patient

    def _update_existing_record(self, record_id: str, record_data: Dict) -> None:
        patient = self.patient_records[record_id]
        new_entries = record_data.get('medical_history')
        if isinstance(new_entries, list):
            for entry in new_entries:
                if isinstance(entry, dict):
                    patient.add_medical_entry(entry)
        self._merge_unique_items(patient, 'allergies', record_data)
        self._merge_unique_items(patient, 'medications', record_data)

    @staticmethod
    def _merge_unique_items(patient: PatientRecord, field: str, record_data: Dict) -> None:
        new_items = record_data.get(field)
        if isinstance(new_items, list):
            merged = list(set(getattr(patient, field) + new_items))
            setattr(patient, field, merged)

    def _log_audit(self, event_type: str, details: str) -> None:
        self.audit_log.append({
            'timestamp': datetime.datetime.now(),
            'event_type': event_type,
            'details': details,
        })

    def export_records(self, record_ids: List[str]) -> bytes:
        export_data = {
            record_id: self._serialize_record(self.patient_records[record_id])
            for record_id in record_ids
            if record_id in self.patient_records
        }
        return json.dumps(export_data).encode('utf-8')

    @staticmethod
    def _serialize_record(patient: PatientRecord) -> Dict:
        return {
            'patient_id': patient.patient_id,
            'name': patient.name,
            'dob': patient.dob,
            'medical_history': patient.medical_history,
            'allergies': patient.allergies,
            'medications': patient.medications,
            'last_updated': patient.last_updated.isoformat(),
        }

    def get_record(self, record_id: str) -> Optional[PatientRecord]:
        return self.patient_records.get(record_id)

    def verify_record_integrity(self, record_id: str) -> bool:
        if record_id not in self.patient_records:
            return False
        patient = self.patient_records[record_id]
        return patient.record_hash == patient._calculate_hash()


class HospitalSystem:
    """High-level facade used by the command-line interface."""

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
        if record is None:
            print('Patient record not found')
            return
        print(f'\nPatient: {record.name} (ID: {record.patient_id})')
        print(f'DOB: {record.dob}')
        print(f"Allergies: {', '.join(record.allergies)}")
        print(f"Medications: {', '.join(record.medications)}")
        print(f'Last Updated: {record.last_updated}')


def main():
    system = HospitalSystem()
    print('Hospital Records Management System')
    while True:
        print('\n1. Import patient records')
        print('2. View patient record')
        print('3. Exit')
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
