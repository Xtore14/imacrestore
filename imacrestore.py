# iMacRestore v1.0.0
# A tool to restore customs IPSWs for Intel-based Macs
# Currently device supported: iMac14,1 (iMac Late 2013 (21.5 inches), 2,7 GHz)

import os
import sys
import zipfile
import shutil
import json
import hashlib
import struct

from datetime import datetime
from tkinter import *
from tkinter import filedialog
from time import sleep as wait

import subprocess

from datetime import datetime

def gpt_disk(target_disk, mode):
  print(f"\nPartitioning {target_disk} as GPT ({mode})...")

  if os.name == "nt":
    disk_num = target_disk.replace("\\\\.\\PhysicalDrive", "")

    if mode == "USBDrive":
      ps_script = f"""
            Clear-Disk -Number {disk_num} -RemoveData -RemoveOEM -Confirm:$false -ErrorAction SilentlyContinue
            Initialize-Disk -Number {disk_num} -PartitionStyle GPT -ErrorAction SilentlyContinue
            New-Partition -DiskNumber {disk_num} -Size 200MB -GptType '{{c12a7328-f81f-11d2-ba4b-00a0c93ec93b}}' | Out-Null
            New-Partition -DiskNumber {disk_num} -UseMaximumSize -GptType '{{48465300-0000-11AA-AA11-00306543ECAC}}' | Out-Null
            """
    elif mode == "TargetDiskMode":
      ps_script = f"""
            Clear-Disk -Number {disk_num} -RemoveData -RemoveOEM -Confirm:$false -ErrorAction SilentlyContinue
            Initialize-Disk -Number {disk_num} -PartitionStyle GPT -ErrorAction SilentlyContinue
            New-Partition -DiskNumber {disk_num} -Size 200MB -GptType '{{c12a7328-f81f-11d2-ba4b-00a0c93ec93b}}' | Out-Null
            $maxSize = (Get-Disk -Number {disk_num}).LargestFreeExtent - 2621440000
            New-Partition -DiskNumber {disk_num} -Size $maxSize -GptType '{{48465300-0000-11AA-AA11-00306543ECAC}}' | Out-Null
            New-Partition -DiskNumber {disk_num} -UseMaximumSize -GptType '{{48465300-0000-11AA-AA11-00306543ECAC}}' | Out-Null
            """

    subprocess.run(["powershell", "-Command", ps_script], check=True)

  elif sys.platform.startswith("linux"):
    subprocess.run(["sgdisk", "--zap-all", target_disk], check=True)
    subprocess.run(
        ["sgdisk", "-n", "1:0:+200M", "-t", "1:EF00", target_disk], check=True
    )
    if mode == "USBDrive":
      subprocess.run(
          ["sgdisk", "-n", "2:0:0", "-t", "2:AF00", target_disk], check=True
      )
    elif mode == "TargetDiskMode":
      subprocess.run(
          ["sgdisk", "-n", "2:0:-2500M", "-t", "2:AF00", target_disk], check=True
      )
      subprocess.run(
          ["sgdisk", "-n", "3:0:0", "-t", "3:AF00", target_disk], check=True
      )

  elif sys.platform == "darwin":
    if mode == "USBDrive":
      # Crea EFI + 1 partizione principale JHFS+ su tutto il disco
      subprocess.run(
          [
              "diskutil",
              "partitionDisk",
              target_disk,
              "GPT",
              "JHFS+",
              "iMacRestore",
              "0b",
          ],
          check=True,
      )
    elif mode == "TargetDiskMode":
      # Crea EFI + Macintosh HD (spazio rimanente) + BaseSystem (2.5 GB)
      subprocess.run(
          [
              "diskutil",
              "partitionDisk",
              target_disk,
              "GPT",
              "JHFS+",
              "Macintosh HD",
              "R",
              "JHFS+",
              "BaseSystem",
              "2500M",
          ],
          check=True,
      )

  print("GPT partition table created successfully!")

def run_backup(base_dir, mode, os_version):
  backup_info_path = os.path.join(base_dir, ".backup", "BackupInfo.json")

  if not os.path.exists(backup_info_path):
    return

  with open(backup_info_path, "r") as f:
    data = json.load(f)

  # 1. Controlla se è abilitato e se siamo in Target Disk Mode
  if not data.get("enabled", False) or mode != "TargetDiskMode":
    return

  ibackup = data.get("iRestoreBackup", {})
  status = ibackup.get("Status", "Unknown")

  print(f"\n--- iRestoreBackup ({ibackup.get('Version')}) [{status}] ---")
  print("[!] Warning: Large User folders may require significant disk space.")

  choice = input("Do you want to backup User data before erasing? (y/n)\n\n> ")
  if choice.lower() != "y":
    print("Skipping backup...")
    return

  # 2. Chiede diskname e username per compilare il percorso del JSON
  diskname = input("Enter Mac Volume Name (e.g., Macintosh HD): ").strip()
  username = input("Enter macOS Username to backup: ").strip()

  # Converte "10.15.7" o "11.7.10" in una tupla di numeri, es. (10, 15, 7) o (11, 7, 10)
  ver_tuple = tuple(map(int, os_version.split(".")))

  # Da 10.15 in poi (inclusi 11, 12, 13, 14, 15...) usa il volume "- Data"
  if ver_tuple >= (10, 15):
    template = ibackup.get("BackupDir10.15")
  else:
    template = ibackup.get("BackupDirDefault")

  source_path = template.format(diskname=diskname, username=username)

  # Su Windows adatta il percorso se l'utente usa un driver con lettera di unità
  if os.name == "nt" and not os.path.exists(source_path):
    drive_letter = input(
        "Enter Windows Drive Letter for iMac volume (e.g., D): "
    ).strip(":\\")
    source_path = os.path.join(f"{drive_letter}:\\", "Users", username)

  if not os.path.exists(source_path):
    print(f"[!] Error: Path '{source_path}' not found or not readable.")
    if input("Continue restore WITHOUT backup? (YES): ") != "YES":
      sys.exit(0)
    return

  # 3. Comprime in backup/
  os.makedirs("backup", exist_ok=True)
  timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
  zip_name = os.path.join("backup", f"iRestoreBackup_{username}_{timestamp}.zip")

  print(f"\nCompressing {source_path} -> {zip_name}...")
  with zipfile.ZipFile(zip_name, "w", zipfile.ZIP_DEFLATED) as zipf:
    for root, dirs, files in os.walk(source_path):
      for file in files:
        full_path = os.path.join(root, file)
        rel_path = os.path.relpath(full_path, source_path)
        try:
          zipf.write(full_path, rel_path)
        except PermissionError:
          pass

  print("Backup completed!\nProceding restore...")

import shutil


def flash_basesystem(bs_dmg, target_disk, mode):
  print(f"\nFlashing {os.path.basename(bs_dmg)} to {target_disk} ({mode})...")

  # Determina il numero della partizione di destinazione (2 per USB, 3 per Target Disk Mode)
  part_num = 2 if mode == "USBDrive" else 3

  if sys.platform == "darwin":
    # Normalizza il percorso del disco su macOS (es. "disk2" -> "/dev/disk2")
    if not target_disk.startswith("/dev/"):
      target_disk = f"/dev/{target_disk}"
    target_part = f"{target_disk}s{part_num}"

    # Prepara il checksum dell'immagine per asr (ignora eventuali errori su DMG di sola lettura)
    subprocess.run(["asr", "imagescan", "--source", bs_dmg], check=False)

    # Smonta il volume target prima del ripristino per evitare errori di "Resource busy"
    subprocess.run(["diskutil", "unmount", target_part], check=False)

    print(f"Restoring image to {target_part} via Apple Software Restore...")
    subprocess.run(
        [
            "asr",
            "restore",
            "--source",
            bs_dmg,
            "--target",
            target_part,
            "--erase",
            "--noprompt",
            "--noverify",
        ],
        check=True,
    )

  else:
    # Su Windows e Linux estraiamo prima il filesystem HFS+ grezzo dal .dmg tramite 7-Zip
    raw_dir = os.path.join("extracted", "raw_image")
    if os.path.exists(raw_dir):
      shutil.rmtree(raw_dir)
    os.makedirs(raw_dir, exist_ok=True)

    seven_zip = (
        "C:\\Program Files\\7-Zip\\7z.exe"
        if os.name == "nt" and os.path.exists("C:\\Program Files\\7-Zip\\7z.exe")
        else "7z"
    )
    print("Decompressing Apple image...")
    # Estrae tutti i file interni al DMG (alcuni BaseSystem contengono *.hfs, altri *.img o file senza estensione)
    subprocess.run(
        [seven_zip, "e", "-tDmg", bs_dmg, f"-o{raw_dir}", "-y"],
        check=True,
    )

    # Trova il file HFS+ estratto (è sempre il file più grande estratto dal DMG)
    hfs_file = None
    max_size = 0
    for f in os.listdir(raw_dir):
      fp = os.path.join(raw_dir, f)
      if os.path.isfile(fp) and os.path.getsize(fp) > max_size:
        max_size = os.path.getsize(fp)
        hfs_file = fp

    if not hfs_file:
      print("Error: Could not extract raw HFS+ image from BaseSystem.dmg.")
      sys.exit(1)

    if os.name == "nt":
      # Su Windows troviamo l'offset in byte della partizione target tramite PowerShell
      disk_num = target_disk.replace("\\\\.\\PhysicalDrive", "")
      ps_cmd = (
          f"(Get-Partition -DiskNumber {disk_num} | Sort-Object"
          " PartitionNumber | Select-Object -Last 1).Offset"
      )
      offset = int(
          subprocess.check_output(["powershell", "-Command", ps_cmd]).strip()
      )

      print(
          f"Writing system image to {target_disk} at offset {offset} bytes..."
      )
      # Scrittura diretta a blocchi (multipli di 4096 byte obbligatori su Windows raw disk)
      with open(hfs_file, "rb") as src, open(target_disk, "r+b") as dst:
        dst.seek(offset)
        while True:
          chunk = src.read(1024 * 1024)  # 1 MB per volta
          if not chunk:
            break
          # Allinea l'ultimo blocco a 4096 byte se necessario
          if len(chunk) % 4096 != 0:
            chunk += b"\x00" * (4096 - (len(chunk) % 4096))
          dst.write(chunk)

    elif sys.platform.startswith("linux"):
      # Su Linux gestisce sia /dev/sdX2 che /dev/nvme0n1p2
      sep = "p" if target_disk[-1].isdigit() else ""
      target_part = f"{target_disk}{sep}{part_num}"
      print(f"Writing raw image to {target_part}...")
      subprocess.run(
          [
              "dd",
              f"if={hfs_file}",
              f"of={target_part}",
              "bs=4M",
              "status=progress",
          ],
          check=True,
      )

  print("Restore image flashed successfully!")
  print("You can now disconnect the drive and boot your Mac holding Option (Alt).")


def select_target_disk():
  print("\nAvailable Disks:\n")

  if os.name == "nt":
    cmd = [
        "powershell",
        "-Command",
        (
            "Get-Disk | Select-Object Number, FriendlyName, @{Name='Size(GB)';"
            " Expression={[math]::Round($_.Size/1GB, 2)}} | Format-Table"
            " -AutoSize"
        ),
    ]
    subprocess.run(cmd)
    disk_num = input("Enter the Disk Number to format/restore (e.g., 1): ")
    return f"\\\\.\\PhysicalDrive{disk_num}"

  elif sys.platform == "darwin":
    subprocess.run(["diskutil", "list"])
    disk_id = input(
        "\nEnter the Disk Identifier to format/restore (e.g., disk2): "
    )
    return f"/dev/{disk_id}"

  elif sys.platform == "linux":
    subprocess.run(["lsblk", "-o", "NAME,MODEL,SIZE,TYPE"])
    disk_id = input("\nEnter the Disk Name to format/restore (e.g., sdb): ")
    return f"/dev/{disk_id}"


def chunklist(dmg_path, chunklist_path):
  if not os.path.exists(dmg_path) or not os.path.exists(chunklist_path):
    return False

  with open(chunklist_path, "rb") as cl:
    header = cl.read(36)
    magic, header_len, version, method, chunk_count, chunk_offset, sig_offset = (
        struct.unpack("<4sIIIIQQ", header)
    )

    if magic != b"CNKL":
      return False

    cl.seek(chunk_offset)
    with open(dmg_path, "rb") as dmg:
      for _ in range(chunk_count):
        chunk_info = cl.read(40)
        chunk_size, expected_hash = struct.unpack("<Q32s", chunk_info)

        data = dmg.read(chunk_size)
        if hashlib.sha256(data).digest() != expected_hash:
          return False

  return True


def choose_ipsw():
  root = Tk()
  root.withdraw()
  root.attributes("-topmost", True)

  file_path = filedialog.askopenfilename(
      title="Select IPSW file", filetypes=[("IPSW files", "*.ipsw")]
  )
  root.destroy()
  return file_path

def Restore():
  print("imacrestore Restore tool (v1.0.0)\n\n")
  restore_menu = input("Options:\n\n1. Restore by IPSW file\n2. Exit\n\n> ")
  if restore_menu == "2":
    sys.exit(0)
  elif restore_menu == "1":
    file = choose_ipsw()
    if not file:
      print("No IPSW file selected.")
      wait(1)
      sys.exit(0)

    extract_folder = "extracted"
    print(f"Extracting {os.path.basename(file)}...")
    os.makedirs(extract_folder, exist_ok=True)
    copy_ipsw = os.path.join(extract_folder, os.path.basename(file))
    shutil.copy2(file, copy_ipsw)
    zip_path = os.path.splitext(copy_ipsw)[0] + ".zip"
    os.replace(copy_ipsw, zip_path)
    print(f"Extracting {os.path.basename(zip_path)}...")
    with zipfile.ZipFile(zip_path, "r") as zip_ref:
      zip_ref.extractall(extract_folder)

    # Trova automaticamente la cartella principale estratta
    base_dir = None
    for root_dir, dirs, files in os.walk(extract_folder):
      if "BuildManifest.json" in files:
        base_dir = root_dir
        break

    if not base_dir:
      print("Error: BuildManifest.json not found in IPSW.")
      sys.exit(0)

    restore_info_path = os.path.join(
        base_dir, ".imacrestore", "RestoreInfo.json"
    )
    manifest_path = os.path.join(base_dir, "BuildManifest.json")

    with open(restore_info_path, "r") as f:
      restore_info = json.load(f)

    with open(manifest_path, "r") as f:
      manifest = json.load(f)

    # Estrazione dati chiave
    model = manifest.get("SMBIOS")
    version = manifest.get("Version")
    build = manifest.get("BuildID")
    supported_targets = restore_info["iMacRestoreInfo"].get(
        "SupportedRestoreTargets", []
    )

    # Percorsi dei file DMG e Chunklist
    bs_dmg = os.path.join(base_dir, manifest["RestoreInfo"]["BaseSystem"])
    bs_cl = os.path.join(base_dir, manifest["RestoreInfo"]["Chunklist"])

    # Verifica integrità tramite chunklist se richiesta in RestoreInfo.json
    if restore_info["iMacRestoreInfo"].get("checkipswvalidate"):
      print("Verifying IPSW integrity...")

      if not chunklist(bs_dmg, bs_cl):
        print("Error: System verification failed!")
        sys.exit(1)

      diag_info = manifest["RestoreInfo"]["Diagnostics"]
      diag_dmg = os.path.join(
          base_dir, "Diagnostics", diag_info["AppleDiagnostics"]
      )
      diag_cl = os.path.join(base_dir, "Diagnostics", diag_info["Chunklist"])

      if not chunklist(diag_dmg, diag_cl):
        print("Error: Diagnostics verification failed!")
        sys.exit(0)

    print(f"\nIPSW for: {model}\nSystem Version: {version} ({build})\n")

    # Scelta del tipo di target basata su RestoreInfo.json
    target_type = input(
        "Select Restore Target:\n\n1. USB Drive (min 16gb)\n2. Target Mode"
        " Disk\n\n> "
    )

    if target_type == "1":
      if "USBDrive" not in supported_targets or not manifest.get(
          "CanRestoreUSB"
      ):
        print("Error: This IPSW does not support USB Restore.")
        sys.exit(1)
      mode = "USBDrive"
    elif target_type == "2":
      if "TargetDiskMode" not in supported_targets:
        print("Error: This IPSW does not support Target Disk Mode.")
        sys.exit(1)
      mode = "TargetDiskMode"
    else:
      print("Invalid target")
      wait(1)
      sys.exit(0)

    # Selezione del disco fisico (cross-platform)
    target_disk = select_target_disk()

    # Backup opzionale PRIMA della formattazione
    run_backup(base_dir, mode, version)

    # Conferma finale prima di cancellare il disco
    print(f"\n[!] WARNING: All data on {target_disk} ({mode}) will be erased!")
    confirm = input("Type 'YES' to continue: ")

    if confirm != "YES":
      print("Restore cancelled.")
      sys.exit(0)

    print(f"\nReady to restore {os.path.basename(bs_dmg)} to {target_disk}...")
    wait(1)
    gpt_disk(target_disk, mode)
    wait(1)
    flash_basesystem(bs_dmg, target_disk, mode)



os.system("cls" if os.name == "nt" else "clear")

menu = "iMacRestore 1.0.0\n\nSimply restore tool for intel-based macs.\n\nOptions:"

print(menu)
menu_input = input(" 1. Restore\n 2. Supported devices list\n 3. Exit\n\n> ")
if menu_input == "1":
    os.system("cls" if os.name == "nt" else "clear")
    Restore()
elif menu_input == "2":
    print("Supported devices:\n\n - iMac Late 2013 (21,5 inches) 2,7 GHz  --> iMac14,1\n")
    wait(3)
    sys.exit(0)
elif menu_input == "3":
    # os.system("cls" if os.name == "nt" else "clear")
    print("\n\nHave a nice day!")
    wait(0.5)
    sys.exit(0)
