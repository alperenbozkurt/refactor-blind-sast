import pickle
import hashlib
import datetime
from typing import Dict, List, Optional


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

    def add_medical_entry(self, entry: Dict) -> None:
        self.medical_history.append(entry)
        self.last_updated = datetime.datetime.now()
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
            self._log_audit('IMPORT_FAILURE', str(e))
            return False

    def _process_imported_records(self, records_data: Dict) -> bool:
        for record_id, record_data in records_data.items():
            try:
                self._import_record(record_id, record_data)
            except Exception as e:
                self._log_audit('IMPORT_ERROR', f'{record_id}: {e}')
        return True

    def _import_record(self, record_id: str, record_data: Dict) -> None:
        if 'patient_id' not in record_data or 'name' not in record_data:
            raise ValueError('Invalid record format')
        if record_id in self.patient_records:
            self._update_existing_record(record_id, record_data)
        else:
            self._create_new_record(record_id, record_data)
        self.imported_data_cache[record_id] = record_data
        self._log_audit('RECORD_IMPORTED', record_id)

    def _create_new_record(self, record_id: str, record_data: Dict) -> None:
        patient = PatientRecord(
            patient_id=record_data['patient_id'],
            name=record_data['name'],
            dob=record_data.get('dob', ''),
        )
        for field in ('medical_history', 'allergies', 'medications'):
            if field in record_data:
                setattr(patient, field, record_data[field])
        self.patient_records[record_id] = patient

    def _update_existing_record(self, record_id: str, record_data: Dict) -> None:
        patient = self.patient_records[record_id]
        if 'medical_history' in record_data:
            for entry in record_data['medical_history']:
                patient.add_medical_entry(entry)
        for field in ('allergies', 'medications'):
            if field in record_data:
                merged = list(set(getattr(patient, field) + record_data[field]))
                setattr(patient, field, merged)

    def _log_audit(self, event_type: str, details: str) -> None:
        self.audit_log.append({
            'timestamp': datetime.datetime.now(),
            'event_type': event_type,
            'details': details,
        })

    def export_records(self, record_ids: List[str]) -> bytes:
        fields = (
            'patient_id', 'name', 'dob', 'medical_history',
            'allergies', 'medications', 'last_updated',
        )
        export_data = {}
        for record_id in record_ids:
            if record_id in self.patient_records:
                patient = self.patient_records[record_id]
                export_data[record_id] = {
                    field: getattr(patient, field) for field in fields
                }
        return pickle.dumps(export_data)

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
            system.import_patient_data(input('Enter import file path: '))
        elif choice == '2':
            system.display_patient_info(input('Enter patient record ID: '))
        elif choice == '3':
            break
        else:
            print('Invalid option')


if __name__ == '__main__':
    main()
