# iMacRestore

**A new way to recover Intel-based Macs using custom IPSW packages.**

iMacRestore is a lightweight Python utility designed to simplify the recovery and restoration process for legacy Intel Macs. By packing standard macOS recovery images (`BaseSystem.dmg`), hardware diagnostics, and SMBIOS metadata into a unified custom `.ipsw` format, it enables structured restores via **Target Disk Mode** or **bootable USB**.

---

## Key Features

* **Custom IPSW Architecture:** Bundles `BaseSystem.dmg`, chunklists, diagnostics, and JSON manifests (`BuildManifest.json` & `RestoreInfo.json`) into a single portable archive.
* **SMBIOS Verification:** Automatically validates target hardware compatibility before initiating any disk operations to prevent accidental flashes.
* **Flexible Restore Targets:** Supports direct restoration to an Intel Mac connected in **Target Disk Mode** as well as creating **bootable USB** recovery media.
* **Cross-Platform GUI File Picker:** Built-in native file dialog (`tkinter`) to easily load `.ipsw` packages on Windows, macOS, and Linux.
* **Version-Aware Backup Handling:** Automatically adapts directory structures for legacy OS X (HFS+) and modern macOS (APFS `- Data` volume split).

---

## Tested Devices

| Model | Identifier | Board ID |
| :--- | :--- | :--- |
| **iMac (21.5-inch, Late 2013) 2.7 GHz** | `iMac14,1` | `Mac-031B6874CF7F642A` |

---

## Custom IPSW Structure

A valid iMacRestore `.ipsw` archive follows this internal layout:

```text
iMac14,1_10.15.7_19H15_Restore.ipsw
├── BuildManifest.json       # Target SMBIOS, OS version, build ID, and image paths
├── RestoreInfo.json         # Validation flags, partition schemes, and backup rules
├── BaseSystem.dmg           # macOS Recovery disk image
├── BaseSystem.chunklist     # Integrity verification file (optional for legacy OS X)
└── Diagnostics/             # Apple Diagnostics / Hardware Test images (optional)
```

---

## Getting Started

### Prerequisites
* **Python 3.9+**
* `tkinter` (included by default on Windows and macOS; on Debian/Ubuntu run `sudo apt install python3-tk`)

### Usage

1. Run the tool as administrator:
   _Linux and macOS:_
   ```bash
   sudo python imacrestore.py
   ```
   _Windows:_
   Run CMD or Powershell as administrator
   ```bash
   python imacrestore.py
   ```
2. Select **Restore**, pick an intel `.ipsw` file from the file manager, and follow the on-screen prompts.

---

## Disclaimer

This tool performs low-level disk and partition operations. Always back up important data before restoring a target drive or USB media. This is an independent project and is not affiliated with Apple Inc.
