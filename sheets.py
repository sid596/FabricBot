# sheets.py

import gspread
from google.oauth2.service_account import Credentials

SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive"
]

creds = Credentials.from_service_account_file(
    "fabricbot.json",
    scopes=SCOPES
)

client = gspread.authorize(creds)

sheet = client.open("Curtains Q2 and July 2025")

worksheet = sheet.worksheet("data")

values = worksheet.get_all_values()

headers = values[0]
rows = values[1:]