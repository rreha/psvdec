import os
import sys
import subprocess
import shutil
import json
import urllib.request
import csv
import io
from rich.console import Console
import platform

console = Console()

def pause_cli():
    if sys.platform.startswith("win32"):
        os.system("pause")
    else:
        input("Press ENTER to continue...")

def print_exit(txt):
    console.print(f"[bold red]{txt}[/bold red]")
    pause_cli()
    if os.path.isdir("./tmp"):
        shutil.rmtree("./tmp")
    sys.exit()

def clear_screen():
    if sys.platform.startswith("win32"):
        os.system("cls")
    else:
        os.system("clear")

def psvpfsparser():
    arch = platform.machine().lower()
    
    if sys.platform.startswith("win32"):
        if arch == "amd64" or arch == "x86_64":
            return "./bin/win64/psvpfsparser.exe"
        else:
            return "./bin/win/psvpfsparser.exe"
            
    elif sys.platform.startswith("darwin"):
        if arch == "arm64" or arch == "aarch64":
            return "./bin/macarm64/psvpfsparser"
        else:
            return "./bin/mac64/psvpfsparser"
            
    elif sys.platform.startswith("linux"):
        return "./bin/ubuntu64/psvpfsparser"

def fetch_nps_database(is_dlc):
    json_file = "dlc.json" if is_dlc else "games.json"
    url = "https://nopaystation.com/tsv/PSV_DLCS.tsv" if is_dlc else "https://nopaystation.com/tsv/PSV_GAMES.tsv"
    
    console.print(f"[bold yellow]> Missing {json_file}. Downloading latest TSV from NoPayStation...[/bold yellow]")
    
    try:
        req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
        with urllib.request.urlopen(req) as response:
            tsv_data = response.read().decode('utf-8')
            
        db = {}
        reader = csv.reader(io.StringIO(tsv_data), delimiter='\t')
        headers = next(reader)
        
        title_id_idx = headers.index('Title ID')
        zrif_idx = headers.index('zRIF')
        content_id_idx = headers.index('Content ID') if 'Content ID' in headers else -1
        
        for row in reader:
            if len(row) <= zrif_idx: continue
            zrif = row[zrif_idx]
            if not zrif or zrif == "MISSING": continue
            
            title_id = row[title_id_idx]

            if is_dlc and content_id_idx != -1 and len(row) > content_id_idx:
                content_id = row[content_id_idx]
                dlc_id = content_id.split('-')[-1]

                if title_id not in db:
                    db[title_id] = {}
                    
                db[title_id][dlc_id] = zrif
            else:
                db[title_id] = zrif
                
        with open(json_file, 'w', encoding='utf-8') as f:
            json.dump(db, f, indent=4)
            
        console.print(f"[bold green]> Successfully converted and saved {json_file}.[/bold green]\n")
        
    except Exception as e:
        print_exit(f"/!\\ Failed to download or parse {url}: {e}")

def ensure_databases():
    if not os.path.exists("games.json"):
        fetch_nps_database(is_dlc=False)
    if not os.path.exists("dlc.json"):
        fetch_nps_database(is_dlc=True)

def extract_pkg(pkg):
    os.makedirs("./tmp", exist_ok=True)
    subprocess.run([sys.executable, "util/nopkg.py", pkg, "ux", "./tmp/"], stdout=subprocess.PIPE, stderr=subprocess.STDOUT)

def detect_content(i):
    basename = os.path.basename(i)
    if basename == "addcont":
        return True
    elif basename in ("app", "patch"):
        return False
    else:
        return None

def get_content_id(i):
    content_id_list = []
    if not os.path.isdir(i):
        return content_id_list
    for folder in os.listdir(i):
        path = os.path.join(i, folder)
        if os.path.isdir(path) and folder.startswith("PCS"):
            content_id_list.append(folder)
    return content_id_list

def get_dlc_id(i, content_id):
    dlc_id_list = []
    path = os.path.join(i, content_id)
    if os.path.isdir(path):
        for dlc in os.listdir(path):
            if os.path.isdir(os.path.join(path, dlc)):
                dlc_id_list.append(dlc)
    return dlc_id_list

def get_zrif(content_id, is_dlc, status_cb, dlc_id=None):
    status_cb("Searching zRIF...")
    json_file = "dlc.json" if is_dlc else "games.json"
    missing_values = (None, '-', 'MISSING')
    
    try:
        with open(json_file, 'r', encoding='utf-8') as f:
            db = json.load(f)
    except Exception:
        status_cb(f"[bold red]Error reading {json_file}[/bold red]")
        return None

    zrif = None

    if is_dlc and dlc_id:
        if content_id in db and isinstance(db[content_id], dict):
            zrif = db[content_id].get(dlc_id)
        elif dlc_id in db:
            zrif = db.get(dlc_id)
    else:
        zrif = db.get(content_id)

    if isinstance(zrif, str):
        zrif = zrif.strip()

    if zrif and zrif not in missing_values:
        return zrif
    else:
        status_cb("[bold red]zRIF key missing from DB[/bold red]")
        return None

def decrypt_pfs(i, content_id, zrif, dlc_id=None, status_cb=None, output_dir="./Decrypted"):
    content = os.path.basename(i)
    
    if content == "addcont":
        out_path = os.path.join(output_dir, content, content_id, dlc_id)
        in_path = os.path.join(i, content_id, dlc_id)
    else:        
        out_path = os.path.join(output_dir, content, content_id)
        in_path = os.path.join(i, content_id)

    if os.path.isdir(out_path):
        shutil.rmtree(out_path)

    if not os.path.exists(os.path.join(in_path, "sce_pfs")):
        status_cb("No encryption layer. Copying directly...")
        shutil.copytree(in_path, out_path)
        return out_path

    os.makedirs(out_path, exist_ok=True)
    status_cb("Decrypting PFS...")
    
    ret = subprocess.run([psvpfsparser(), "-i", in_path, "-o", out_path, "-z", zrif, "-f", "cma.henkaku.xyz"], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    ret_str = str(ret.stdout) + str(ret.stderr)

    if "invalid" in ret_str:
        if os.path.isdir(out_path):
            shutil.rmtree(out_path)
        status_cb("[bold red]Header signature invalid (Bad zRIF?)[/bold red]")
        return None
            
    elif "failed to find unicv.db" in ret_str:
        if os.path.isdir(out_path):
            shutil.rmtree(out_path)
        status_cb("[bold red]Missing unicv.db[/bold red]")
        return None
    
    return out_path

def decrypt_eboot(zrif, target_folder, status_cb):
    os.makedirs("./tmp", exist_ok=True)
    eboot_path = os.path.join(target_folder, "eboot.bin")
    decrypted_path = os.path.join(target_folder, "eboot_decrypted.bin")
    
    unique_id = os.path.basename(target_folder)
    work_bin = f"./tmp/work_{unique_id}.bin"

    if os.path.exists(eboot_path) and not os.path.exists(decrypted_path):
        status_cb("Decrypting eboot.bin...")
        subprocess.run([sys.executable, "util/zzzrif.py", zrif, work_bin], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        subprocess.run([sys.executable, "./util/self2elf.py", "-i", eboot_path, "-o", decrypted_path, "-k", work_bin], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        
        if not os.path.isfile(decrypted_path):
            status_cb("[bold red]eboot decryption failed[/bold red]")
            return False
            
        if os.path.exists(work_bin):
            os.remove(work_bin)
            
    return True

def process_item(task, status_callback, output_dir="./Decrypted", no_eboot=False):
    folder, content_id, is_dlc, dlc_id, identifier = task
    
    zrif = get_zrif(content_id, is_dlc, status_cb=status_callback, dlc_id=dlc_id)
    if not zrif:
        return

    if is_dlc:
        out_path = decrypt_pfs(folder, content_id, zrif, dlc_id=dlc_id, status_cb=status_callback, output_dir=output_dir)
        if out_path:
            display_path = os.path.normpath(out_path)
            status_callback(f"[bold green]✔ ({display_path})[/bold green]")
    else:
        out_path = decrypt_pfs(folder, content_id, zrif, status_cb=status_callback, output_dir=output_dir)
        if out_path:
            if not no_eboot:
                eboot_success = decrypt_eboot(zrif, out_path, status_cb=status_callback)
                if not eboot_success:
                    return
                    
            display_path = os.path.normpath(out_path)
            status_callback(f"[bold green]✔ ({display_path})[/bold green]")