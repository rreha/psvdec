import os
import sys
import shutil
import argparse
from concurrent.futures import ThreadPoolExecutor
from rich.live import Live
from rich.table import Table
from rich.console import Console
import threading

from psvdec import *

console = Console()
task_statuses = {}
status_lock = threading.Lock()

def update_status(identifier, status_text):
    with status_lock:
        task_statuses[identifier] = status_text

def generate_table():
    table = Table(show_header=False, box=None, padding=(0, 1))
    table.add_column("Prefix", style="bold white", justify="left")
    table.add_column("Item", style="bold medium_purple3", justify="left")
    table.add_column("Status", style="white", justify="left")

    with status_lock:
        for identifier, status in task_statuses.items():
            table.add_row(">", identifier, f": {status}")
    return table

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="psvdec ~ PS Vita Content Decryptor")
    parser.add_argument("inputs", nargs="*", help="PS Vita .pkg files or folders (app/patch/addcont)")
    parser.add_argument("-o", "--out", default="./Decrypted", help="Output directory for decrypted content (default: ./Decrypted)")
    parser.add_argument("--no-eboot", action="store_true", help="Disable eboot.bin decryption")
    parser.add_argument("--update-db", action="store_true", help="Force update of zRIF databases")
    args = parser.parse_args()

    if not args.inputs and not args.update_db:
        print_exit("/!\\ Please specify at least one PS Vita .pkg file or folder.\nUse -h for help.")

    try:
        if os.path.isdir("./tmp"):
            shutil.rmtree("./tmp")

        clear_screen()
        console.print("[bold medium_purple3]psvdec ~ PS Vita Content Decryptor ~ https://github.com/rreha/psvdec[/bold medium_purple3]\n")

        ensure_databases(force_update=args.update_db)

        if not args.inputs:
            sys.exit(0)

        inputs = args.inputs
        pkgs_to_extract = [i for i in inputs if os.path.isfile(i) and i.lower().endswith(".pkg")]
        folders_to_process = [i for i in inputs if os.path.isdir(i)]

        if pkgs_to_extract:
            console.print(f"[bold white]> Extracting {len(pkgs_to_extract)} PKG file(s)...[/bold white]")
            for pkg in pkgs_to_extract:
                extract_pkg(pkg)
                
            if os.path.exists("./tmp/"):
                for item in os.listdir("./tmp/"):
                    full_path = os.path.join("./tmp", item)
                    if os.path.isdir(full_path):
                        folders_to_process.append(full_path)

        folders_to_process = list(set(folders_to_process))
        tasks_queue = []

        for folder in folders_to_process:
            is_dlc = detect_content(folder)
            if is_dlc is None:
                continue

            content_id_list = get_content_id(folder)

            for content_id in content_id_list:
                if is_dlc:
                    content_type = "addcont"
                else:
                    content_type = "app"
                    changeinfo_path = os.path.join(folder, content_id, "sce_sys", "changeinfo", "changeinfo.xml")
                    if os.path.basename(folder) == "patch" or os.path.exists(changeinfo_path):
                        content_type = "patch"

                if is_dlc:
                    dlc_id_list = get_dlc_id(folder, content_id)
                    for dlc_id in dlc_id_list:
                        tasks_queue.append((folder, content_id, is_dlc, dlc_id, f"{content_id}/{dlc_id} ({content_type})"))
                else:
                    tasks_queue.append((folder, content_id, is_dlc, None, f"{content_id} ({content_type})"))

        if tasks_queue:
            for _, _, _, _, identifier in tasks_queue:
                task_statuses[identifier] = "..."

            console.print(f"\n[bold white]> Starting queue for {len(tasks_queue)} item(s):[/bold white]\n")

            with Live(generate_table(), refresh_per_second=10) as live:
                def worker(task):
                    try:
                        process_item(
                            task, 
                            status_callback=lambda msg: (update_status(task[4], msg), live.update(generate_table())),
                            output_dir=args.out,
                            no_eboot=args.no_eboot
                        )
                    except Exception as e:
                        update_status(task[4], f"[bold red]Crash: {str(e)}[/bold red]")
                        live.update(generate_table())

                with ThreadPoolExecutor(max_workers=4) as executor:
                    list(executor.map(worker, tasks_queue))

            console.print("\n[bold green]All operations completed![/bold green]")

    except KeyboardInterrupt:
        console.print("\n[bold red]/!\\ Process aborted by user. Cleaning up...[/bold red]")

    finally:
        if os.path.exists("./tmp"):
            shutil.rmtree("./tmp")