"""Check ZIP integrity of docx/xlsx files locally."""
import zipfile, os, sys

files = [
    r"dongbo\U3listening.docx",
    r"dongbo\note.docx",
    r"dongbo\Testcase.xlsx",
    r"C:\Users\Ad\Downloads\_check_U3listening.docx",
    r"C:\Users\Ad\Downloads\_check_Testcase.xlsx",
    r"C:\Users\Ad\Downloads\U3listening.docx",
]

results = []
for path in files:
    if not os.path.exists(path):
        results.append(f"NOT FOUND: {path}")
        continue
    sz = os.path.getsize(path)
    with open(path, "rb") as f:
        head = f.read(8)
        f.seek(0)
        data = f.read()
    # Check magic
    magic = head[:2]
    is_pk = magic == b"PK"
    # Check EOCD
    eocd = data.rfind(b"PK\x05\x06")
    # Try zipfile
    try:
        with zipfile.ZipFile(path) as z:
            entries = len(z.namelist())
            zip_ok = True
    except Exception as e:
        entries = 0
        zip_ok = False
        zip_err = str(e)
    # Null bytes
    null_count = data.count(b"\x00")
    first_null = data.find(b"\x00")
    line = (f"{os.path.basename(path)}: sz={sz} pk={is_pk} "
            f"eocd={eocd} zip={'OK entries='+str(entries) if zip_ok else 'BAD:'+zip_err} "
            f"nulls={null_count} first_null={first_null}")
    results.append(line)

out = "\n".join(results)
print(out)
with open("_zip_results.txt", "w") as f:
    f.write(out + "\n")
print("\nSaved to _zip_results.txt")
