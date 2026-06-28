import csv, sqlite3

csv_file = "lists/au_removal_list_asin.csv"
db_file  = "db/a_au_blacklist_asin.db"

# CSVのASIN一覧
with open(csv_file, encoding="utf-8") as f:
    reader = csv.reader(f)
    csv_asins = {row[0].strip() for row in reader if row}

# DBのASIN一覧
conn = sqlite3.connect(db_file)
db_asins = {row[0] for row in conn.execute("SELECT asin FROM blacklist_asin")}
conn.close()

# 差分（CSVにあってDBに無いもの）
missing = csv_asins - db_asins
print(f"❌ DBに無いASIN: {len(missing)} 件")
for asin in sorted(missing):
    print(asin)
