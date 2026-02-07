import urllib.request
import csv

SPREADSHEET_ID = "1Muf5Hy6Zq1i8Rty1M26-5u13lalUBsuC-pVXNFXMoYM"
SHEET_GID = "1812502896"
CSV_URL = f"https://docs.google.com/spreadsheets/d/{SPREADSHEET_ID}/export?format=csv&gid={SHEET_GID}"

def main():
    try:
        with urllib.request.urlopen(CSV_URL) as response:
            data = response.read().decode('utf-8')
            reader = csv.reader(data.splitlines())
            for i in range(3):
                row = next(reader, None)
                if row:
                    print(f"Row {i}: {row}")
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    main()
