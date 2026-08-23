import zipfile
import os

def zipdir(path, ziph):
    for root, dirs, files in os.walk(path):
        for file in files:
            filepath = os.path.join(root, file)
            arcname = os.path.relpath(filepath, os.path.dirname(path))
            ziph.write(filepath, arcname)

if __name__ == '__main__':
    base = 'ticket_system'
    out = 'ticket_system.zip'
    with zipfile.ZipFile(out, 'w', zipfile.ZIP_DEFLATED) as z:
        zipdir(base, z)
    print('wrote', out)
