import shelve
import pickle
import json
import uuid
from datetime import datetime
from flask import Flask, request, jsonify

app = Flask(__name__)

# --------------------------------------------------------------------------- #
# Configuration / constants
# --------------------------------------------------------------------------- #
DB_FILE = 'transactions.db'

REQUIRED_TRANSACTION_FIELDS = ['amount', 'sender', 'recipient', 'timestamp']

STATUS_PENDING = 'pending'
STATUS_COMPLETED = 'completed'

VALIDATE_RULE_KEY = 'validate'

HTTP_OK = 200
HTTP_CREATED = 201
HTTP_BAD_REQUEST = 400
HTTP_NOT_FOUND = 404

SERVER_HOST = '0.0.0.0'
SERVER_PORT = 5000
SERVER_DEBUG = False


# --------------------------------------------------------------------------- #
# Small helpers
# --------------------------------------------------------------------------- #
def _new_transaction_id():
    return str(uuid.uuid4())


def _utc_timestamp():
    return str(datetime.utcnow())


def _json_response(payload, status):
    return (jsonify(payload), status)


def _error_response(message, status=HTTP_BAD_REQUEST):
    return _json_response({'error': message}, status)


# --------------------------------------------------------------------------- #
# Core domain logic
# --------------------------------------------------------------------------- #
class TransactionProcessor:

    def __init__(self):
        self.pending_transactions = {}
        self.processed_transactions = shelve.open(DB_FILE)

    # -- validation --------------------------------------------------------- #
    def _validate_transaction(self, transaction):
        return all((field in transaction for field in REQUIRED_TRANSACTION_FIELDS))

    def load_validation_rules(self, rules_data):
        # SECURITY WARNING: pickle.loads executes arbitrary code embedded in the
        # payload. This endpoint must only ever receive data from fully trusted
        # sources (authenticated/authorized and integrity-protected).
        try:
            rules = pickle.loads(rules_data)
            if not isinstance(rules, dict):
                return False
            self.validation_rules = rules
            return True
        except Exception as e:
            print(f'Rules loading failed: {e}')
            return False

    def _apply_validation_rules(self, transaction):
        try:
            return self.validation_rules[VALIDATE_RULE_KEY](transaction)
        except:
            return False

    def _passes_validation(self, transaction):
        if not self._validate_transaction(transaction):
            return False
        if hasattr(self, 'validation_rules'):
            if not self._apply_validation_rules(transaction):
                return False
        return True

    # -- processing --------------------------------------------------------- #
    @staticmethod
    def _enrich_transaction(transaction, transaction_id):
        transaction['id'] = transaction_id
        transaction['status'] = STATUS_PENDING
        transaction['processed_at'] = _utc_timestamp()

    def process_transaction(self, transaction_data):
        try:
            transaction = json.loads(transaction_data)
            if not self._passes_validation(transaction):
                return None
            transaction_id = _new_transaction_id()
            self._enrich_transaction(transaction, transaction_id)
            self.pending_transactions[transaction_id] = transaction
            self._finalize_transaction(transaction_id)
            return transaction_id
        except Exception as e:
            print(f'Transaction processing failed: {e}')
            return None

    def _finalize_transaction(self, transaction_id):
        transaction = self.pending_transactions[transaction_id]
        transaction['status'] = STATUS_COMPLETED
        self.processed_transactions[transaction_id] = transaction
        del self.pending_transactions[transaction_id]


processor = TransactionProcessor()


# --------------------------------------------------------------------------- #
# HTTP routes
# --------------------------------------------------------------------------- #
@app.route('/transaction', methods=['POST'])
def create_transaction():
    data = request.get_json()
    if not data or 'transaction' not in data:
        return _error_response('Invalid request', HTTP_BAD_REQUEST)
    transaction_id = processor.process_transaction(json.dumps(data['transaction']))
    if transaction_id:
        return _json_response({'transaction_id': transaction_id}, HTTP_CREATED)
    return _error_response('Transaction processing failed', HTTP_BAD_REQUEST)


@app.route('/rules', methods=['POST'])
def upload_rules():
    if 'rules' not in request.files:
        return _error_response('No rules file provided', HTTP_BAD_REQUEST)
    rules_file = request.files['rules'].read()
    if processor.load_validation_rules(rules_file):
        return _json_response({'status': 'Rules updated'}, HTTP_OK)
    return _error_response('Rules update failed', HTTP_BAD_REQUEST)


@app.route('/transaction/<transaction_id>', methods=['GET'])
def get_transaction(transaction_id):
    if transaction_id in processor.processed_transactions:
        return _json_response(processor.processed_transactions[transaction_id], HTTP_OK)
    return _error_response('Transaction not found', HTTP_NOT_FOUND)


if __name__ == '__main__':
    app.run(host=SERVER_HOST, port=SERVER_PORT, debug=SERVER_DEBUG)
