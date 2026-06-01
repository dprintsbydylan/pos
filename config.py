import os

class Config:
    SECRET_KEY = os.getenv('SECRET_KEY', 'printing-pos-secret-change-me')
    GOOGLE_SPREADSHEET_ID = os.getenv('GOOGLE_SPREADSHEET_ID', '')
    GOOGLE_CREDENTIALS = os.getenv('GOOGLE_CREDENTIALS', '')
    GOOGLE_CREDENTIALS_FILE = os.getenv('GOOGLE_SHEETS_CREDENTIALS', 'credentials.json')
    DEBUG = os.getenv('FLASK_DEBUG', 'true').lower() == 'true'
    HOST = os.getenv('HOST', '0.0.0.0')
    PORT = int(os.getenv('PORT', 5000))
