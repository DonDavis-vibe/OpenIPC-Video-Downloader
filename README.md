# 🛸 OpenIPC VRX Auto-Sync & Downloader

A cross-platform GUI tool to automate downloading flight footage from your OpenIPC VRX (Video Receiver). 

### Why is this useful?
As an FPV pilot using an OpenIPC digital video system, getting your flight footage off your VRX usually involves a tedious manual process: you have to disconnect your PC from your home Wi-Fi, connect to the VRX's hotspot, open a web browser to `192.168.4.1`, manually download each video file one by one (trying to remember which ones you already downloaded), and then reconnect to your home network.

**This tool completely automates that workflow.** With a single click, it will:
1. Automatically switch your PC's Wi-Fi to your VRX.
2. Scan the VRX web server for new flight videos.
3. Compare the files against your local save folder and skip any you've already downloaded.
4. Download all new videos automatically.
5. Reconnect your PC back to your home Wi-Fi when finished.

## ✨ Features
- 🖥️ **Modern Dark-Mode GUI** — Clean interface built with CustomTkinter.
- 📶 **Auto Wi-Fi Switching** — Automatically connects to your VRX, downloads videos, and reconnects to your Home Wi-Fi when done.
- 🔴/🟢 **Live Connection Status** — Real-time indicator for your VRX connection status.
- 📥 **Smart Downloads** — Skips videos you've already downloaded.
- 🎬 **H.264 Auto-Conversion** — Optionally converts H.265 videos to H.264 on the fly for easier editing.
- 🌍 **Cross-Platform** — Works on Windows, macOS, and Linux.
- 🔔 **Native Notifications** — Get desktop alerts when downloads finish.

## 📋 Requirements
- **Python 3.8+**
- **CustomTkinter** (UI Library)
- **FFmpeg** (Optional, only required for the H.264 auto-conversion feature)

### Installation

**Windows**
1. Ensure you have Python installed. You can download it from [python.org](https://www.python.org/downloads/) or via the Microsoft Store.
2. Open Command Prompt or PowerShell and install the required UI library:
   ```cmd
   pip install customtkinter
   ```
3. Clone or download this repository.

**Linux & macOS**
1. Make sure Python 3 and pip are installed.
2. Install the required dependency:
   ```bash
   pip3 install customtkinter
   ```
3. Clone or download this repository.

## 🚀 Usage

> ⚠️ **Important:** Before running the tool, make sure your VRX is powered on and its **Wi-Fi Hotspot feature is activated** so your PC can connect to it!

### Windows (Easiest)
Simply double-click the **`run_downloader.bat`** file to launch the app!

### Linux & macOS
Run the Python script directly from your terminal:
```bash
python3 openipc_downloader.py
```

### How to Use the GUI
1. **VRX Wi-Fi SSID:** Enter the Wi-Fi name of your VRX (e.g., `OpenIPC GS`).
2. **Home Wi-Fi SSID:** Enter your home internet Wi-Fi name (so the tool can reconnect you later).
3. **Save Folder:** Choose where you want your flight videos saved.
4. Click **`⚡ Start Sync & Download`**!

*If your PC is already connected to the VRX Wi-Fi, you can use the `📥 Download Only` button to skip the Wi-Fi switching step.*

## 📄 License
This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.
