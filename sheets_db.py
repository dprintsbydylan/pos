import os
import json
from datetime import datetime, date
import gspread
from gspread.utils import rowcol_to_a1
from oauth2client.service_account import ServiceAccountCredentials

SCOPE = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]

SHEET_STRUCTURE = {
    "customers": ["id", "name", "phone", "email", "address", "company", "created_at"],
    "products": ["id", "name", "description", "category", "unit_price", "cost_price", "stock_qty", "unit", "is_service", "created_at"],
    "orders": ["id", "order_no", "customer_id", "order_date", "due_date", "status", "subtotal", "tax", "discount", "total", "amount_paid", "payment_status", "notes", "created_at"],
    "order_items": ["id", "order_id", "product_id", "description", "quantity", "unit_price", "subtotal"],
    "payments": ["id", "order_id", "amount", "method", "payment_date", "reference"],
    "expenses": ["id", "date", "description", "category", "amount", "vendor", "payment_method", "receipt_ref", "notes", "created_at"],
    "journal": ["id", "date", "description", "entry_type", "account_name", "debit", "credit", "reference_type", "reference_id", "created_at"],
}


class SheetsDB:
    def __init__(self, spreadsheet_id=None, credentials_dict=None):
        self.spreadsheet_id = spreadsheet_id
        self.credentials_dict = credentials_dict
        self.client = None
        self.spreadsheet = None
        self._id_counters = {}

    def connect(self):
        if self.credentials_dict:
            creds = ServiceAccountCredentials.from_json_keyfile_dict(
                self.credentials_dict, SCOPE
            )
        elif os.getenv('GOOGLE_CREDENTIALS'):
            creds = ServiceAccountCredentials.from_json_keyfile_dict(
                json.loads(os.getenv('GOOGLE_CREDENTIALS')), SCOPE
            )
        else:
            creds = ServiceAccountCredentials.from_json_keyfile_name(
                os.getenv('GOOGLE_SHEETS_CREDENTIALS', 'credentials.json'), SCOPE
            )
        self.client = gspread.authorize(creds)
        sid = self.spreadsheet_id or os.getenv('GOOGLE_SPREADSHEET_ID')
        if not sid:
            raise ValueError("Spreadsheet ID is required. Set GOOGLE_SPREADSHEET_ID env var.")
        self.spreadsheet = self.client.open_by_key(sid)
        self._ensure_structure()

    def _ensure_structure(self):
        existing = {ws.title for ws in self.spreadsheet.worksheets()}
        for name, headers in SHEET_STRUCTURE.items():
            if name not in existing:
                ws = self.spreadsheet.add_worksheet(title=name, rows=1000, cols=len(headers))
                ws.append_row(headers)
            else:
                ws = self.spreadsheet.worksheet(name)
                existing_headers = ws.row_values(1)
                if existing_headers != headers:
                    ws.clear()
                    ws.append_row(headers)
            self._id_counters[name] = self._get_max_id(name)

    def _get_max_id(self, sheet_name):
        ws = self.spreadsheet.worksheet(sheet_name)
        ids = ws.col_values(1)[1:]
        if ids:
            return max(int(i) for i in ids if i.isdigit())
        return 0

    def _next_id(self, sheet_name):
        self._id_counters[sheet_name] = self._id_counters.get(sheet_name, 0) + 1
        return self._id_counters[sheet_name]

    def _ws(self, name):
        return self.spreadsheet.worksheet(name)

    def _headers(self, name):
        return SHEET_STRUCTURE[name]

    def _row_to_dict(self, name, row):
        headers = self._headers(name)
        return {headers[i]: row[i] if i < len(row) else '' for i in range(len(headers))}

    def all(self, sheet_name, order_by=None, desc=True):
        ws = self._ws(sheet_name)
        rows = ws.get_all_values()
        if len(rows) < 2:
            return []
        headers = rows[0]
        result = []
        for row in rows[1:]:
            if row and row[0]:
                d = {headers[i]: row[i] if i < len(row) else '' for i in range(len(headers))}
                self._coerce_types(d)
                result.append(d)
        if order_by and order_by in headers:
            idx = headers.index(order_by)
            result.sort(key=lambda x: str(x.get(order_by, '')), reverse=desc)
        return result

    def get_by_id(self, sheet_name, record_id):
        ws = self._ws(sheet_name)
        try:
            cell = ws.find(str(record_id))
            if cell:
                row = ws.row_values(cell.row)
                d = self._row_to_dict(sheet_name, row)
                self._coerce_types(d)
                return d
        except gspread.exceptions.CellNotFound:
            pass
        return None

    def insert(self, sheet_name, data):
        headers = self._headers(sheet_name)
        record_id = self._next_id(sheet_name)
        data['id'] = str(record_id)
        if 'created_at' in headers and 'created_at' not in data:
            data['created_at'] = datetime.utcnow().isoformat()

        row = [str(data.get(h, '')) for h in headers]
        ws = self._ws(sheet_name)
        ws.append_row(row)
        return record_id

    def update(self, sheet_name, record_id, data):
        ws = self._ws(sheet_name)
        try:
            cell = ws.find(str(record_id))
        except gspread.exceptions.CellNotFound:
            return False
        headers = self._headers(sheet_name)
        row_num = cell.row
        for key, value in data.items():
            if key in headers:
                col = headers.index(key) + 1
                ws.update_cell(row_num, col, str(value))
        return True

    def delete(self, sheet_name, record_id):
        ws = self._ws(sheet_name)
        try:
            cell = ws.find(str(record_id))
            ws.delete_row(cell.row)
            return True
        except gspread.exceptions.CellNotFound:
            return False

    def filter(self, sheet_name, **kwargs):
        all_records = self.all(sheet_name)
        result = all_records
        for key, value in kwargs.items():
            result = [r for r in result if r.get(key) == value]
        return result

    def query(self, sheet_name, conditions=None, order_by=None, desc=True, limit=None):
        all_records = self.all(sheet_name)
        if conditions:
            for key, value in conditions.items():
                all_records = [r for r in all_records if str(r.get(key, '')) == str(value)]
        if order_by:
            all_records.sort(key=lambda x: str(x.get(order_by, '')), reverse=desc)
        if limit:
            all_records = all_records[:limit]
        return all_records

    def sum(self, sheet_name, field, conditions=None):
        records = self.query(sheet_name, conditions)
        total = 0
        for r in records:
            try:
                total += float(r.get(field, 0) or 0)
            except (ValueError, TypeError):
                pass
        return total

    def count(self, sheet_name, conditions=None):
        return len(self.query(sheet_name, conditions))

    def _coerce_types(self, d):
        for key in ['id', 'customer_id', 'product_id', 'order_id', 'reference_id']:
            if key in d and d[key]:
                try:
                    d[key] = int(d[key])
                except ValueError:
                    pass
        for key in ['unit_price', 'cost_price', 'stock_qty', 'subtotal', 'tax', 'discount', 'total', 'amount_paid', 'amount', 'debit', 'credit', 'quantity']:
            if key in d and d[key]:
                try:
                    d[key] = float(d[key])
                except ValueError:
                    pass
        return d
