import json
import hashlib
import datetime
from typing import Dict, List, Optional

_UTF8 = 'utf-8'
_STATE_INDENT = 2
_DEFAULT_ACCOUNT_BALANCE = 1000.0
_REQUIRED_TRANSACTION_FIELDS = ('sender', 'recipient', 'amount')

_EVENT_BATCH_LOAD_FAILURE = 'BATCH_LOAD_FAILURE'
_EVENT_TRANSACTION_QUEUED = 'TRANSACTION_QUEUED'
_EVENT_TRANSACTION_REJECTED = 'TRANSACTION_REJECTED'
_EVENT_TRANSACTION_PROCESSED = 'TRANSACTION_PROCESSED'
_EVENT_TRANSACTION_FAILED = 'TRANSACTION_FAILED'
_EVENT_STATE_LOAD_ERROR = 'STATE_LOAD_ERROR'


def _load_json_bytes(batch_data: bytes):
    try:
        return json.loads(batch_data.decode(_UTF8))
    except json.JSONDecodeError as e:
        raise ValueError(f'Invalid JSON format: {str(e)}')


def _parse_timestamp(timestamp_str):
    if timestamp_str:
        try:
            return datetime.datetime.fromisoformat(timestamp_str)
        except ValueError:
            raise ValueError('Invalid timestamp format')
    return datetime.datetime.now()


def _make_audit_entry(event_type: str, details: str) -> Dict:
    return {
        'timestamp': datetime.datetime.now(),
        'event_type': event_type,
        'details': details,
    }


def _serialize_audit_entry(entry: Dict) -> Dict:
    return {
        'timestamp': entry['timestamp'].isoformat(),
        'event_type': entry['event_type'],
        'details': entry['details'],
    }


def _deserialize_audit_entry(entry: Dict) -> Dict:
    return {
        'timestamp': datetime.datetime.fromisoformat(entry['timestamp']),
        'event_type': entry['event_type'],
        'details': entry['details'],
    }


class Transaction:

    def __init__(self, sender: str, recipient: str, amount: float, timestamp: datetime.datetime):
        self.sender = sender
        self.recipient = recipient
        self.amount = amount
        self.timestamp = timestamp
        self.transaction_id = self._generate_id()
        self.signature: Optional[str] = None

    def _generate_id(self) -> str:
        data = f'{self.sender}{self.recipient}{self.amount}{self.timestamp}'
        return hashlib.sha256(data.encode()).hexdigest()

    def to_dict(self) -> Dict:
        return {
            'sender': self.sender,
            'recipient': self.recipient,
            'amount': self.amount,
            'timestamp': self.timestamp.isoformat(),
            'transaction_id': self.transaction_id,
            'signature': self.signature,
        }


def _transaction_from_batch_data(tx_data: Dict) -> Transaction:
    if not isinstance(tx_data, dict):
        raise ValueError('Transaction must be a dictionary')
    if not all((field in tx_data for field in _REQUIRED_TRANSACTION_FIELDS)):
        raise ValueError('Missing required transaction fields')

    timestamp = _parse_timestamp(tx_data.get('timestamp'))
    tx = Transaction(
        sender=str(tx_data['sender']),
        recipient=str(tx_data['recipient']),
        amount=float(tx_data['amount']),
        timestamp=timestamp,
    )
    if 'signature' in tx_data:
        tx.signature = str(tx_data['signature'])
    return tx


def _transaction_from_state(tx_data: Dict) -> Transaction:
    tx = Transaction(
        sender=tx_data['sender'],
        recipient=tx_data['recipient'],
        amount=tx_data['amount'],
        timestamp=datetime.datetime.fromisoformat(tx_data['timestamp']),
    )
    tx.transaction_id = tx_data['transaction_id']
    tx.signature = tx_data.get('signature')
    return tx


class TransactionProcessor:

    def __init__(self):
        self.pending_transactions: List[Transaction] = []
        self.processed_transactions: Dict[str, Transaction] = {}
        self.account_balances: Dict[str, float] = {}
        self.audit_log: List[Dict] = []

    def load_transaction_batch(self, batch_data: bytes) -> bool:
        try:
            transactions = _load_json_bytes(batch_data)
            if not isinstance(transactions, list):
                raise ValueError('Transaction batch must be a list')
            return self._process_batch(transactions)
        except Exception as e:
            self._log_audit(_EVENT_BATCH_LOAD_FAILURE, str(e))
            return False

    def _process_batch(self, transactions: List[Dict]) -> bool:
        for tx_data in transactions:
            try:
                tx = _transaction_from_batch_data(tx_data)
                self._validate_transaction(tx)
                self.pending_transactions.append(tx)
                self._log_audit(_EVENT_TRANSACTION_QUEUED, tx.transaction_id)
            except Exception as e:
                self._log_audit(_EVENT_TRANSACTION_REJECTED, str(e))
        return True

    def _ensure_account(self, account_id: str) -> None:
        if account_id not in self.account_balances:
            self.account_balances[account_id] = _DEFAULT_ACCOUNT_BALANCE

    def _validate_transaction(self, tx: Transaction) -> None:
        if tx.amount <= 0:
            raise ValueError('Invalid transaction amount')
        if not isinstance(tx.sender, str) or not tx.sender:
            raise ValueError('Invalid sender')
        if not isinstance(tx.recipient, str) or not tx.recipient:
            raise ValueError('Invalid recipient')

        self._ensure_account(tx.sender)
        self._ensure_account(tx.recipient)

        if self.account_balances[tx.sender] < tx.amount:
            raise ValueError('Insufficient funds')

    def _apply_transaction(self, tx: Transaction) -> None:
        self.account_balances[tx.sender] -= tx.amount
        self.account_balances[tx.recipient] += tx.amount
        self.processed_transactions[tx.transaction_id] = tx

    def process_pending_transactions(self) -> None:
        for tx in self.pending_transactions:
            try:
                self._apply_transaction(tx)
                self._log_audit(_EVENT_TRANSACTION_PROCESSED, tx.transaction_id)
            except Exception as e:
                self._log_audit(_EVENT_TRANSACTION_FAILED, str(e))
        self.pending_transactions.clear()

    def _log_audit(self, event_type: str, details: str) -> None:
        self.audit_log.append(_make_audit_entry(event_type, details))

    def get_balance(self, account_id: str) -> float:
        return self.account_balances.get(account_id, 0.0)

    def _serialize_state(self) -> Dict:
        return {
            'processed_transactions': {
                tx_id: tx.to_dict()
                for (tx_id, tx) in self.processed_transactions.items()
            },
            'account_balances': self.account_balances,
            'audit_log': [_serialize_audit_entry(entry) for entry in self.audit_log],
        }

    def save_state(self, file_path: str) -> None:
        state = self._serialize_state()
        with open(file_path, 'w', encoding=_UTF8) as f:
            json.dump(state, f, indent=_STATE_INDENT)

    def _load_processed_transactions(self, transactions_state: Dict) -> None:
        for (tx_id, tx_data) in transactions_state.items():
            try:
                self.processed_transactions[tx_id] = _transaction_from_state(tx_data)
            except Exception as e:
                self._log_audit(
                    _EVENT_STATE_LOAD_ERROR,
                    f'Failed to load transaction {tx_id}: {str(e)}',
                )

    def _load_audit_entries(self, audit_state: List[Dict]) -> None:
        for entry in audit_state:
            try:
                self.audit_log.append(_deserialize_audit_entry(entry))
            except Exception as e:
                self._log_audit(
                    _EVENT_STATE_LOAD_ERROR,
                    f'Failed to load audit entry: {str(e)}',
                )

    def load_state(self, file_path: str) -> None:
        with open(file_path, 'r', encoding=_UTF8) as f:
            state = json.load(f)
            self.processed_transactions = {}
            self._load_processed_transactions(state['processed_transactions'])
            self.account_balances = state['account_balances']
            self.audit_log = []
            self._load_audit_entries(state['audit_log'])


class FinancialSystem:

    def __init__(self):
        self.processor = TransactionProcessor()

    def process_transaction_file(self, file_path: str) -> None:
        try:
            with open(file_path, 'rb') as f:
                data = f.read()
                if self.processor.load_transaction_batch(data):
                    self.processor.process_pending_transactions()
                    print('Transactions processed successfully')
                else:
                    print('Failed to process transactions')
        except Exception as e:
            print(f'Error processing file: {str(e)}')

    def print_balances(self) -> None:
        print('\nAccount Balances:')
        for (account, balance) in self.processor.account_balances.items():
            print(f'{account}: {balance:.2f}')

    def print_audit_log(self, num_entries: int = 5) -> None:
        print(f'\nLast {num_entries} audit entries:')
        for entry in self.processor.audit_log[-num_entries:]:
            print(f"{entry['timestamp']} - {entry['event_type']}: {entry['details']}")


def main():
    system = FinancialSystem()
    print('Financial Transaction System')
    while True:
        print('\n1. Process transaction file')
        print('2. Show account balances')
        print('3. Show audit log')
        print('4. Exit')
        choice = input('Select option: ').strip()
        if choice == '1':
            file_path = input('Enter transaction file path: ').strip()
            if not file_path:
                print('Error: File path cannot be empty')
                continue
            system.process_transaction_file(file_path)
        elif choice == '2':
            system.print_balances()
        elif choice == '3':
            system.print_audit_log()
        elif choice == '4':
            break
        else:
            print('Invalid option')


if __name__ == '__main__':
    main()
