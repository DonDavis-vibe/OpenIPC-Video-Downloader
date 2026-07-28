import os
import sys
import time
import re
import threading
import subprocess
import platform
import urllib.request
import urllib.parse
import json
import datetime
from html.parser import HTMLParser
import customtkinter as ctk
from tkinter import filedialog, messagebox

# Set app styling
ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("blue")

VIDEO_EXTENSIONS = ('.mp4', '.ts', '.mov', '.mkv', '.avi', '.h264', '.h265')
OS_NAME = platform.system()

class HTMLDirectoryParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.links = []

    def handle_starttag(self, tag, attrs):
        if tag == 'a':
            for name, value in attrs:
                if name == 'href' and value:
                    self.links.append(value)

def get_current_wifi_ssid():
    """Returns the currently connected Wi-Fi SSID, or None. Cross-platform."""
    try:
        if OS_NAME == "Windows":
            output = subprocess.check_output(["netsh", "wlan", "show", "interfaces"], text=True, encoding="cp850", errors="ignore")
            match = re.search(r"SSID\s*:\s*(.+)", output)
            if match:
                ssid = match.group(1).strip()
                if ssid and "BSSID" not in ssid:
                    return ssid
        elif OS_NAME == "Darwin":
            output = subprocess.check_output(["networksetup", "-getairportnetwork", "en0"], text=True, errors="ignore")
            if "Current Wi-Fi Network" in output:
                return output.split(":")[1].strip()
        elif OS_NAME == "Linux":
            output = subprocess.check_output(["iwgetid", "-r"], text=True, errors="ignore")
            return output.strip()
    except Exception:
        pass
    return None

def connect_to_wifi(ssid):
    """Attempts to connect to the specified Wi-Fi profile. Cross-platform."""
    try:
        if OS_NAME == "Windows":
            cmd = f'netsh wlan connect name="{ssid}"'
            subprocess.run(cmd, shell=True, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            return True
        elif OS_NAME == "Darwin":
            cmd = f'networksetup -setairportnetwork en0 "{ssid}"'
            subprocess.run(cmd, shell=True, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            return True
        elif OS_NAME == "Linux":
            cmd = f'nmcli dev wifi connect "{ssid}"'
            subprocess.run(cmd, shell=True, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            return True
    except Exception:
        return False
    return False

def show_os_toast(title, message):
    """Triggers a native OS desktop notification."""
    try:
        if OS_NAME == "Windows":
            ps_script = f'''
            [Windows.UI.Notifications.ToastNotificationManager, Windows.UI.Notifications, ContentType = WindowsRuntime] | Out-Null
            [Windows.Data.Xml.Dom.XmlDocument, Windows.Data.Xml.Dom.XmlDocument, ContentType = WindowsRuntime] | Out-Null
            $template = [Windows.UI.Notifications.ToastNotificationManager]::GetTemplateContent([Windows.UI.Notifications.ToastTemplateType]::ToastText02)
            $xml = [Windows.Data.Xml.Dom.XmlDocument]::new()
            $xml.LoadXml($template.GetXml())
            $textNodes = $xml.GetElementsByTagName("text")
            $textNodes.Item(0).AppendChild($xml.CreateTextNode("{title}")) | Out-Null
            $textNodes.Item(1).AppendChild($xml.CreateTextNode("{message}")) | Out-Null
            $toast = [Windows.UI.Notifications.ToastNotification]::new($xml)
            [Windows.UI.Notifications.ToastNotificationManager]::CreateToastNotifier("OpenIPC Downloader").Show($toast)
            '''
            subprocess.run(["powershell", "-Command", ps_script], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        elif OS_NAME == "Darwin":
            cmd = f'osascript -e \'display notification "{message}" with title "{title}"\''
            subprocess.run(cmd, shell=True)
        elif OS_NAME == "Linux":
            subprocess.run(["notify-send", title, message])
    except Exception:
        pass


class VRXFileManagerWindow(ctk.CTkToplevel):
    def __init__(self, parent, vrx_url, vrx_ssid):
        super().__init__(parent)
        self.parent = parent
        self.vrx_url = vrx_url
        self.vrx_ssid = vrx_ssid
        self.title("VRX File Manager - SD Card Cleanup")
        self.geometry("700x520")
        self.minsize(600, 420)
        
        self.transient(parent)
        self.grab_set()

        top_frame = ctk.CTkFrame(self, fg_color="transparent")
        top_frame.pack(fill="x", padx=15, pady=(15, 10))
        
        title_lbl = ctk.CTkLabel(top_frame, text="📂 VRX SD Card Videos", font=ctk.CTkFont(size=16, weight="bold"))
        title_lbl.pack(side="left")
        
        self.refresh_btn = ctk.CTkButton(top_frame, text="🔄 Refresh", width=90, command=self.load_videos, fg_color="#3B82F6", hover_color="#2563EB")
        self.refresh_btn.pack(side="right", padx=(5, 0))

        self.delete_all_btn = ctk.CTkButton(top_frame, text="🗑️ Delete All", width=100, command=self.delete_all_videos, fg_color="#EF4444", hover_color="#DC2626")
        self.delete_all_btn.pack(side="right")

        self.status_lbl = ctk.CTkLabel(self, text="Connecting to VRX...", font=ctk.CTkFont(size=12), text_color="#F59E0B")
        self.status_lbl.pack(fill="x", padx=15, pady=(0, 5))

        self.list_frame = ctk.CTkScrollableFrame(self, corner_radius=10)
        self.list_frame.pack(fill="both", expand=True, padx=15, pady=(0, 15))

        self.video_rows = []
        self.load_videos()

    def load_videos(self):
        self.status_lbl.configure(text="Scanning VRX for videos...", text_color="#F59E0B")
        self.refresh_btn.configure(state="disabled")
        self.delete_all_btn.configure(state="disabled")
        
        for child in self.list_frame.winfo_children():
            child.destroy()
        self.video_rows.clear()

        import threading
        threading.Thread(target=self._scan_thread, daemon=True).start()

    def _scan_thread(self):
        try:
            url_base = self.vrx_url.strip()
            if not url_base.endswith('/'): url_base += '/'
            
            found = []
            try:
                try:
                    req = urllib.request.urlopen(url_base, timeout=3)
                except Exception:
                    if self.vrx_ssid:
                        self.after(0, lambda: self.status_lbl.configure(text=f"Switching Wi-Fi to '{self.vrx_ssid}'...", text_color="#F59E0B"))
                        connect_to_wifi(self.vrx_ssid)
                        import time; time.sleep(3)
                        req = urllib.request.urlopen(url_base, timeout=4)
                    else:
                        raise
                html = req.read().decode('utf-8', errors='ignore')
                class LinkParser(HTMLParser):
                    def __init__(self, base):
                        super().__init__()
                        self.base = base
                        self.links = set()
                    def handle_starttag(self, tag, attrs):
                        if tag == 'a' or tag == 'source':
                            for k, v in attrs:
                                if k in ('href', 'src') and v and v.lower().endswith(('.mp4', '.mov')):
                                    full = urllib.parse.urljoin(self.base, v)
                                    self.links.add(full)

                parser = LinkParser(url_base)
                parser.feed(html)
                found = sorted(list(parser.links))
            except Exception as e:
                self.after(0, lambda: self.status_lbl.configure(text=f"Error connecting to VRX: {e}", text_color="#EF4444"))
                self.after(0, lambda: self.refresh_btn.configure(state="normal"))
                return

            if not found:
                self.after(0, lambda: self.status_lbl.configure(text="No videos found on VRX SD Card.", text_color="#10B981"))
                self.after(0, lambda: self.refresh_btn.configure(state="normal"))
                return

            target_dir = self.parent.save_dir.get().strip()
            history_path = os.path.join(target_dir, ".sync_history.json")
            sync_history = {}
            if os.path.exists(history_path):
                try:
                    with open(history_path, "r", encoding="utf-8") as f:
                        sync_history = json.load(f)
                except Exception:
                    pass

            local_files = os.listdir(target_dir) if os.path.exists(target_dir) else []

            video_info = []
            for idx, v_url in enumerate(found):
                fname = os.path.basename(urllib.parse.unquote(v_url))
                size_str = "Unknown size"
                size_bytes = 0
                try:
                    req = urllib.request.Request(v_url, method='HEAD')
                    with urllib.request.urlopen(req, timeout=2) as resp:
                        size_bytes = int(resp.headers.get('Content-Length', 0))
                        if size_bytes > 0:
                            size_str = f"{size_bytes / (1024*1024):.1f} MB"
                except Exception:
                    pass

                is_saved = False
                status_text = "⚠️ NOT DOWNLOADED"
                status_color = "#EF4444" # Red

                if fname in sync_history and (size_bytes == 0 or sync_history[fname].get('remote_size', -1) in (size_bytes, 0)):
                    is_saved = True
                    status_text = "✅ Saved"
                    status_color = "#10B981"
                else:
                    base_no_ext, ext = os.path.splitext(fname)
                    for lf in local_files:
                        if lf == fname or lf.endswith("_" + fname):
                            is_saved = True
                            status_text = "✅ Saved"
                            status_color = "#10B981"
                            break
                        if lf == f"{base_no_ext}_h264{ext}" or lf.endswith(f"_{base_no_ext}_h264{ext}"):
                            is_saved = True
                            status_text = "✅ Saved (H.264)"
                            status_color = "#10B981"
                            break

                video_info.append((fname, size_str, is_saved, status_text, status_color))

            self.after(0, lambda: self._populate_list(video_info))
        except Exception as e:
            self.after(0, lambda: self.status_lbl.configure(text=f"Scan error: {e}", text_color="#EF4444"))
            self.after(0, lambda: self.refresh_btn.configure(state="normal"))

    def _populate_list(self, video_info):
        self.status_lbl.configure(text=f"Found {len(video_info)} video(s) on VRX.", text_color="#10B981")
        self.refresh_btn.configure(state="normal")
        if video_info:
            self.delete_all_btn.configure(state="normal")

        for fname, size_str, is_saved, status_text, status_color in video_info:
            row_frame = ctk.CTkFrame(self.list_frame, fg_color=("#2B2B2B", "#1F1F1F"), corner_radius=8)
            row_frame.pack(fill="x", pady=4, padx=4)

            name_lbl = ctk.CTkLabel(row_frame, text=fname, font=ctk.CTkFont(size=13, weight="bold"), anchor="w")
            name_lbl.pack(side="left", padx=12, pady=10, fill="x", expand=True)

            size_lbl = ctk.CTkLabel(row_frame, text=size_str, font=ctk.CTkFont(size=12), text_color="gray", width=70)
            size_lbl.pack(side="left", padx=5)

            status_lbl = ctk.CTkLabel(row_frame, text=status_text, font=ctk.CTkFont(size=12, weight="bold"), text_color=status_color, width=140)
            status_lbl.pack(side="left", padx=10)

            del_btn = ctk.CTkButton(row_frame, text="🗑️ Delete", width=80, height=32, fg_color="#EF4444", hover_color="#DC2626",
                                    command=lambda f=fname, rf=row_frame, saved=is_saved: self.delete_single_video(f, rf, saved))
            del_btn.pack(side="right", padx=10, pady=6)
            self.video_rows.append((fname, row_frame, is_saved))

    def delete_single_video(self, fname, row_frame, is_saved):
        if not is_saved:
            msg = f"⚠️ WARNING: '{fname}' has NOT been downloaded to your PC yet!\n\nAre you sure you want to permanently delete un-saved footage from the VRX?"
        else:
            msg = f"Are you sure you want to delete '{fname}' from the VRX?"
        if not messagebox.askyesno("Confirm Delete", msg):
            return
        
        self.status_lbl.configure(text=f"Deleting {fname}...", text_color="#F59E0B")
        
        def _del_thread():
            try:
                url_base = self.vrx_url.strip()
                if not url_base.endswith('/'): url_base += '/'
                del_url = f"{url_base}delete/{urllib.parse.quote(fname)}"
                urllib.request.urlopen(del_url, timeout=5)
                
                def _on_success():
                    row_frame.destroy()
                    self.video_rows = [r for r in self.video_rows if r[0] != fname]
                    self.status_lbl.configure(text=f"Deleted {fname}", text_color="#10B981")
                    if not self.video_rows:
                        self.delete_all_btn.configure(state="disabled")
                self.after(0, _on_success)
            except Exception as e:
                self.after(0, lambda: self.status_lbl.configure(text=f"Failed to delete {fname}: {e}", text_color="#EF4444"))

        import threading
        threading.Thread(target=_del_thread, daemon=True).start()

    def delete_all_videos(self):
        if not self.video_rows:
            return
        unsaved_count = sum(1 for item in self.video_rows if not item[2])
        if unsaved_count > 0:
            msg = f"⚠️ WARNING: {unsaved_count} of the {len(self.video_rows)} video(s) have NOT been downloaded to your PC yet!\n\nAre you sure you want to PERMANENTLY DELETE all videos including un-saved footage?"
        else:
            msg = f"Are you sure you want to PERMANENTLY DELETE all {len(self.video_rows)} video(s) from the VRX SD Card?"
        if not messagebox.askyesno("Confirm Delete All", msg):
            return
        
        self.status_lbl.configure(text="Deleting all videos...", text_color="#F59E0B")
        self.delete_all_btn.configure(state="disabled")
        self.refresh_btn.configure(state="disabled")

        def _del_all_thread():
            deleted_count = 0
            url_base = self.vrx_url.strip()
            if not url_base.endswith('/'): url_base += '/'

            import time
            for fname, row_frame, is_saved in list(self.video_rows):
                try:
                    del_url = f"{url_base}delete/{urllib.parse.quote(fname)}"
                    urllib.request.urlopen(del_url, timeout=5)
                    deleted_count += 1
                    self.after(0, row_frame.destroy)
                except Exception as e:
                    print(f"Error deleting {fname}: {e}")
                time.sleep(0.1)

            self.after(0, lambda: self.status_lbl.configure(text=f"Deleted {deleted_count} video(s).", text_color="#10B981"))
            self.after(0, lambda: self.refresh_btn.configure(state="normal"))
            self.after(0, self.load_videos)

        import threading
        threading.Thread(target=_del_all_thread, daemon=True).start()

class OpenIPCFlightDownloader(ctk.CTk):

    def __init__(self):
        super().__init__()

        self.title("OpenIPC VRX Flight Downloader & Auto-Sync")
        self.geometry("720x670")
        self.minsize(680, 580)
        self.resizable(True, True)

        # Default Config
        self.vrx_ssid = ctk.StringVar(value="OpenIPC GS")
        self.home_ssid = ctk.StringVar(value="18E9")
        self.vrx_url = ctk.StringVar(value="http://192.168.4.1/")
        
        default_save_path = os.path.join(os.path.expanduser("~"), "Videos", "OpenIPC_Flights")
        self.save_dir = ctk.StringVar(value=default_save_path)
        self.auto_reconnect = ctk.BooleanVar(value=True)
        self.convert_h264 = ctk.BooleanVar(value=False)
        self.delete_original = ctk.BooleanVar(value=False)
        self.delete_from_vrx = ctk.BooleanVar(value=False)

        self.is_running = False
        self.stop_requested = False
        self.job_start_time = 0
        self.file_start_time = 0
        self.current_idx = 0
        self.total_to_dl = 0
        self._last_eta_update = 0

        self._create_widgets()

        # Start live background connection status monitor thread
        self.monitor_active = True
        threading.Thread(target=self._connection_monitor_loop, daemon=True).start()

    def _create_widgets(self):
        # Top Header
        header_frame = ctk.CTkFrame(self, corner_radius=10)
        header_frame.pack(fill="x", padx=15, pady=(12, 6))

        # Title + Status Light Row
        title_row = ctk.CTkFrame(header_frame, fg_color="transparent")
        title_row.pack(fill="x", padx=15, pady=(8, 2))

        title_label = ctk.CTkLabel(title_row, text="🛸 OpenIPC VRX Auto-Sync", font=ctk.CTkFont(size=20, weight="bold"))
        title_label.pack(side="left")

        # Connection Indicator Badge (Green / Red Status Light)
        self.status_badge = ctk.CTkLabel(
            title_row, 
            text="🔴 VRX Offline", 
            font=ctk.CTkFont(size=12, weight="bold"),
            fg_color="#7F1D1D", 
            text_color="#FCA5A5",
            corner_radius=12,
            padx=10, 
            pady=4
        )
        self.status_badge.pack(side="right")

        sub_label = ctk.CTkLabel(header_frame, text="Automated flight video sync & Wi-Fi management", font=ctk.CTkFont(size=12), text_color="gray")
        sub_label.pack(anchor="w", padx=15, pady=(0, 8))

        # Config Card
        config_frame = ctk.CTkFrame(self, corner_radius=10)
        config_frame.pack(fill="x", padx=15, pady=6)

        # VRX Wi-Fi
        ctk.CTkLabel(config_frame, text="VRX Wi-Fi SSID:", font=ctk.CTkFont(size=12, weight="bold")).grid(row=0, column=0, sticky="w", padx=12, pady=6)
        ctk.CTkEntry(config_frame, textvariable=self.vrx_ssid, width=170).grid(row=0, column=1, sticky="w", padx=5, pady=6)

        # Home Wi-Fi
        ctk.CTkLabel(config_frame, text="Home Wi-Fi SSID:", font=ctk.CTkFont(size=12, weight="bold")).grid(row=0, column=2, sticky="w", padx=12, pady=6)
        ctk.CTkEntry(config_frame, textvariable=self.home_ssid, width=170).grid(row=0, column=3, sticky="w", padx=5, pady=6)

        # VRX URL
        ctk.CTkLabel(config_frame, text="VRX Web Server:", font=ctk.CTkFont(size=12, weight="bold")).grid(row=1, column=0, sticky="w", padx=12, pady=6)
        ctk.CTkEntry(config_frame, textvariable=self.vrx_url, width=170).grid(row=1, column=1, sticky="w", padx=5, pady=6)

        # Quick Reconnect to Home Wi-Fi Button
        home_reconnect_btn = ctk.CTkButton(config_frame, text="📶 Reconnect Home Wi-Fi", font=ctk.CTkFont(size=11),
                                           fg_color="#374151", hover_color="#4B5563", width=170, command=self._manual_reconnect_home)
        home_reconnect_btn.grid(row=1, column=3, sticky="w", padx=5, pady=6)

        # Save Directory
        ctk.CTkLabel(config_frame, text="Save Folder:", font=ctk.CTkFont(size=12, weight="bold")).grid(row=2, column=0, sticky="w", padx=12, pady=6)
        dir_entry = ctk.CTkEntry(config_frame, textvariable=self.save_dir, width=340)
        dir_entry.grid(row=2, column=1, columnspan=2, sticky="we", padx=5, pady=6)
        
        browse_btn = ctk.CTkButton(config_frame, text="Browse", width=80, command=self._browse_folder)
        browse_btn.grid(row=2, column=3, sticky="w", padx=5, pady=6)

        # Options (2-row layout)
        options_frame = ctk.CTkFrame(config_frame, fg_color="transparent")
        options_frame.grid(row=3, column=0, columnspan=4, sticky="w", padx=12, pady=(4, 10))
        
        opt_row1 = ctk.CTkFrame(options_frame, fg_color="transparent")
        opt_row1.pack(fill="x", pady=(0, 4))
        reconnect_chk = ctk.CTkCheckBox(opt_row1, text="Auto-reconnect to Home Wi-Fi", variable=self.auto_reconnect)
        reconnect_chk.pack(side="left", padx=(0, 20))
        convert_chk = ctk.CTkCheckBox(opt_row1, text="Auto-convert H.265 to H.264 (Requires FFmpeg)", variable=self.convert_h264)
        convert_chk.pack(side="left")

        opt_row2 = ctk.CTkFrame(options_frame, fg_color="transparent")
        opt_row2.pack(fill="x", pady=(2, 0))
        delete_chk = ctk.CTkCheckBox(opt_row2, text="Delete local H.265 after conversion", variable=self.delete_original)
        delete_chk.pack(side="left", padx=(0, 20))
        delete_vrx_chk = ctk.CTkCheckBox(opt_row2, text="🗑️ Auto-delete from VRX SD card after sync", variable=self.delete_from_vrx, fg_color="#EF4444", hover_color="#DC2626", command=self._on_delete_from_vrx_toggle)
        delete_vrx_chk.pack(side="left")

        # Bottom Action Buttons Frame (Packed FIRST at bottom!)
        btn_frame = ctk.CTkFrame(self, fg_color="transparent")
        btn_frame.pack(side="bottom", fill="x", padx=15, pady=(6, 12))

        self.start_btn = ctk.CTkButton(btn_frame, text="⚡ Start Sync", font=ctk.CTkFont(size=14, weight="bold"),
                                        fg_color="#10B981", hover_color="#059669", height=44, command=self.start_sync_thread)
        self.start_btn.pack(side="left", fill="x", expand=True, padx=(0, 3))

        self.quick_download_btn = ctk.CTkButton(btn_frame, text="📥 Download Only", font=ctk.CTkFont(size=12, weight="bold"),
                                                fg_color="#3B82F6", hover_color="#2563EB", height=44, command=lambda: self.start_sync_thread(skip_wifi=True))
        self.quick_download_btn.pack(side="left", fill="x", expand=True, padx=3)

        self.manage_vrx_btn = ctk.CTkButton(btn_frame, text="📂 Manage VRX Files", font=ctk.CTkFont(size=12, weight="bold"),
                                            fg_color="#F59E0B", hover_color="#D97706", height=44, command=self.open_file_manager)
        self.manage_vrx_btn.pack(side="left", fill="x", expand=True, padx=3)

        # Abort Button (Initially Disabled)
        self.abort_btn = ctk.CTkButton(btn_frame, text="⛔ Abort", font=ctk.CTkFont(size=13, weight="bold"),
                                        fg_color="#EF4444", hover_color="#DC2626", height=44, state="disabled", command=self.request_abort)
        self.abort_btn.pack(side="right", fill="x", expand=True, padx=(3, 0))

        # Status & Progress Frame (Takes remaining space)
        status_frame = ctk.CTkFrame(self, corner_radius=10)
        status_frame.pack(side="top", fill="both", expand=True, padx=15, pady=6)

        self.status_lbl = ctk.CTkLabel(status_frame, text="Status: Ready", font=ctk.CTkFont(size=13, weight="bold"), text_color="#3B82F6")
        self.status_lbl.pack(anchor="w", padx=12, pady=(8, 0))

        self.eta_lbl = ctk.CTkLabel(status_frame, text="", font=ctk.CTkFont(size=11), text_color="gray")
        self.eta_lbl.pack(anchor="w", padx=12, pady=(0, 4))

        self.job_progress_lbl = ctk.CTkLabel(status_frame, text="Overall Job Progress: Idle", font=ctk.CTkFont(size=11, weight="bold"), text_color="#60A5FA")
        self.job_progress_lbl.pack(anchor="w", padx=12, pady=(2, 0))
        self.progress_bar = ctk.CTkProgressBar(status_frame)
        self.progress_bar.pack(fill="x", padx=12, pady=(2, 6))
        self.progress_bar.set(0)

        self.file_progress_lbl = ctk.CTkLabel(status_frame, text="Current File Progress: Idle", font=ctk.CTkFont(size=11, weight="bold"), text_color="#10B981")
        self.file_progress_lbl.pack(anchor="w", padx=12, pady=(2, 0))
        self.file_progress_bar = ctk.CTkProgressBar(status_frame, progress_color="#10B981")
        self.file_progress_bar.pack(fill="x", padx=12, pady=(2, 6))
        self.file_progress_bar.set(0)

        self.log_textbox = ctk.CTkTextbox(status_frame, font=ctk.CTkFont(family="Consolas", size=11))
        self.log_textbox.pack(fill="both", expand=True, padx=12, pady=(4, 8))

    def _on_delete_from_vrx_toggle(self):
        if self.delete_from_vrx.get():
            msg = ("⚠️ RISK WARNING: Automatic VRX SD Card Wiping!\n\n"
                   "Enabling this option will permanently delete each video from your VRX SD card over HTTP "
                   "immediately after it is successfully downloaded and verified on your PC.\n\n"
                   "Make sure your PC's save folder is backed up. Are you sure you want to enable automatic SD card deletion?")
            if not messagebox.askyesno("⚠️ Risk Warning: Auto-Delete from VRX", msg):
                self.delete_from_vrx.set(False)

    def _browse_folder(self):
        selected = filedialog.askdirectory(initialdir=self.save_dir.get())
        if selected:
            self.save_dir.set(selected)

    def _manual_reconnect_home(self):
        home_ssid = self.home_ssid.get().strip()
        if not home_ssid:
            messagebox.showwarning("Missing SSID", "Please specify your Home Wi-Fi SSID first.")
            return
        self.log(f"[*] Switching Wi-Fi back to Home network '{home_ssid}'...")
        if connect_to_wifi(home_ssid):
            self.log("[+] Wi-Fi reconnect command sent.")
        else:
            self.log("[!] Failed to send Wi-Fi reconnect command.")

    def log(self, message):
        self.log_textbox.insert("end", message + "\n")
        self.log_textbox.see("end")

    def update_status(self, text, color="#3B82F6"):
        self.status_lbl.configure(text=f"Status: {text}", text_color=color)

    def _connection_monitor_loop(self):
        """Background thread checking VRX Wi-Fi / HTTP status every 3 seconds."""
        while self.monitor_active:
            try:
                url_base = self.vrx_url.get().strip()
                if not url_base.endswith('/'):
                    url_base += '/'

                is_connected = False
                try:
                    req = urllib.request.urlopen(url_base, timeout=1.5)
                    if req.status == 200:
                        is_connected = True
                except Exception:
                    is_connected = False

                curr_ssid = get_current_wifi_ssid()

                self.after(0, self._update_badge_ui, is_connected, curr_ssid)
            except Exception:
                pass

            time.sleep(3)

    def _update_badge_ui(self, is_connected, curr_ssid):
        vrx_ssid = self.vrx_ssid.get().strip()
        if is_connected:
            self.status_badge.configure(
                text=f"🟢 VRX Connected ({vrx_ssid})",
                fg_color="#065F46",
                text_color="#A7F3D0"
            )
        elif curr_ssid and vrx_ssid.lower() in curr_ssid.lower():
            self.status_badge.configure(
                text=f"🟡 Wi-Fi Connected (Waiting for Server...)",
                fg_color="#92400E",
                text_color="#FDE68A"
            )
        else:
            display_ssid = curr_ssid if curr_ssid else "Disconnected"
            self.status_badge.configure(
                text=f"🔴 VRX Offline ({display_ssid})",
                fg_color="#7F1D1D",
                text_color="#FCA5A5"
            )

    def _format_time(self, seconds):
        if seconds < 0: return "00:00"
        m, s = divmod(int(seconds), 60)
        h, m = divmod(m, 60)
        if h > 0:
            return f"{h:02d}:{m:02d}:{s:02d}"
        return f"{m:02d}:{s:02d}"

    def _format_speed(self, bytes_per_sec):
        if bytes_per_sec >= 1024 * 1024:
            return f"{bytes_per_sec / (1024 * 1024):.1f} MB/s"
        elif bytes_per_sec >= 1024:
            return f"{bytes_per_sec / 1024:.1f} KB/s"
        return f"{bytes_per_sec:.0f} B/s"

    def _update_eta(self, file_prog, speed_text=""):
        now = time.time()
        file_elapsed = now - self.file_start_time
        file_eta = (file_elapsed / file_prog) - file_elapsed if file_prog > 0 else 0
        
        overall_prog = (self.current_idx + file_prog) / self.total_to_dl if self.total_to_dl > 0 else 0
        job_elapsed = now - self.job_start_time
        job_eta = (job_elapsed / overall_prog) - job_elapsed if overall_prog > 0 else 0
        
        job_pct = int(overall_prog * 100)
        self.job_progress_lbl.configure(text=f"Overall Job Progress: {self.current_idx + 1} of {self.total_to_dl} files ({job_pct}%)")
        
        speed_str = f" | Speed: {speed_text}" if speed_text else ""
        eta_text = (f"File: {self._format_time(file_elapsed)} elapsed, ETA: {self._format_time(file_eta)}{speed_str}  |  "
                    f"Job: {self._format_time(job_elapsed)} elapsed, ETA: {self._format_time(job_eta)}")
        
        self.eta_lbl.configure(text=eta_text)

    def open_file_manager(self):
        VRXFileManagerWindow(self, self.vrx_url.get().strip(), self.vrx_ssid.get().strip())

    def request_abort(self):
        if self.is_running:
            self.stop_requested = True
            self.log("[!] Abort requested by user! Stopping after current operation...")
            self.update_status("Aborting sync...", "#EF4444")
            self.abort_btn.configure(state="disabled")

    def start_sync_thread(self, skip_wifi=False):
        if self.is_running:
            return
        self.is_running = True
        self.stop_requested = False

        self.start_btn.configure(state="disabled")
        self.quick_download_btn.configure(state="disabled")
        self.manage_vrx_btn.configure(state="disabled")
        self.abort_btn.configure(state="normal")

        threading.Thread(target=self._run_sync, args=(skip_wifi,), daemon=True).start()

    def _run_sync(self, skip_wifi):
        try:
            target_dir = self.save_dir.get()
            os.makedirs(target_dir, exist_ok=True)
            vrx_ssid = self.vrx_ssid.get().strip()
            home_ssid = self.home_ssid.get().strip()
            url_base = self.vrx_url.get().strip()
            if not url_base.endswith('/'):
                url_base += '/'

            if not skip_wifi:
                if self.stop_requested:
                    return
                self.update_status(f"Connecting to VRX Wi-Fi ({vrx_ssid})...", "#F59E0B")
                self.log(f"[*] Switching Wi-Fi to '{vrx_ssid}'...")
                
                connect_to_wifi(vrx_ssid)

                connected = False
                for attempt in range(12):
                    if self.stop_requested:
                        self.log("[!] Sync aborted during Wi-Fi connection.")
                        return
                    time.sleep(1)
                    curr = get_current_wifi_ssid()
                    if curr and vrx_ssid.lower() in curr.lower():
                        connected = True
                        break
                    self.log(f"    Waiting for Wi-Fi connection... ({attempt + 1}/12)")

                if not connected:
                    self.log(f"[!] Warning: Could not connect to '{vrx_ssid}'.")
                    self.log(f"    -> Have you connected to this VRX manually before?")
                    self.log(f"    -> IMPORTANT: You must connect to the VRX manually at least ONCE so your OS saves the Wi-Fi password!")
                    self.log(f"    -> Attempting server check anyway...")

            if self.stop_requested:
                return

            self.update_status("Contacting VRX Web Server...", "#F59E0B")
            self.log(f"[*] Connecting to VRX server at {url_base}...")
            
            reachable = False
            for attempt in range(8):
                if self.stop_requested:
                    self.log("[!] Sync aborted.")
                    return
                try:
                    req = urllib.request.urlopen(url_base, timeout=3)
                    if req.status == 200:
                        reachable = True
                        break
                except Exception:
                    time.sleep(1)

            if not reachable:
                self.log(f"[X] Error: Cannot reach VRX web server at {url_base}. Is the VRX turned on and Wi-Fi connected?")
                self.update_status("Error: VRX Web Server unreachable", "#EF4444")
                return

            if self.stop_requested:
                return
            self.update_status("Scanning VRX for video files...", "#F59E0B")
            self.log("[*] Crawling VRX directory listing for videos...")
            
            history_path = os.path.join(target_dir, ".sync_history.json")
            sync_history = {}
            if os.path.exists(history_path):
                try:
                    with open(history_path, "r", encoding="utf-8") as f:
                        sync_history = json.load(f)
                except Exception:
                    pass

            found_videos = self._scan_vrx_directory(url_base)
            self.log(f"[+] Found {len(found_videos)} video file(s) on VRX.")

            if not found_videos:
                self.log("[!] No video files found on the VRX web server.")
                self.update_status("No video files found", "#3B82F6")
            else:
                to_download = []
                for v_url in found_videos:
                    if self.stop_requested:
                        break
                    fname = os.path.basename(urllib.parse.unquote(v_url))
                    
                    try:
                        req = urllib.request.Request(v_url, method='HEAD')
                        with urllib.request.urlopen(req, timeout=3) as resp:
                            remote_size = int(resp.headers.get('Content-Length', 0))
                            
                            size_mb = f" ({remote_size/(1024*1024):.1f} MB)" if remote_size > 0 else ""
                            if fname in sync_history and sync_history[fname].get('remote_size') == remote_size:
                                self.log(f"[-] Skipping (in history): {fname}{size_mb}")
                                continue
                            
                            local_path = os.path.join(target_dir, fname)
                            if os.path.exists(local_path) and os.path.getsize(local_path) == remote_size:
                                self.log(f"[-] Skipping (exists locally): {fname}{size_mb}")
                                continue
                                
                    except Exception as e:
                        remote_size = 0
                        
                    today_str = datetime.datetime.now().strftime("%Y-%m-%d")
                    new_fname = f"{today_str}_{fname}"
                    local_path = os.path.join(target_dir, new_fname)
                    
                    to_download.append((v_url, fname, new_fname, local_path, remote_size))

                if self.stop_requested:
                    self.log("[!] Sync aborted by user.")
                    self.update_status("Sync Aborted", "#EF4444")
                    return

                self.log(f"[*] {len(to_download)} new video(s) ready for download.")

                downloaded_count = 0
                self.total_to_dl = len(to_download)
                self.job_start_time = time.time()

                for idx, (v_url, orig_fname, new_fname, local_path, remote_size) in enumerate(to_download):
                    if self.stop_requested:
                        self.log("[!] Download loop aborted by user.")
                        break

                    self.current_idx = idx
                    self.update_status(f"Downloading {idx+1}/{self.total_to_dl}: {new_fname}", "#10B981")
                    size_mb_str = f" ({remote_size/(1024*1024):.1f} MB)" if remote_size > 0 else ""
                    self.log(f"[*] Downloading [{idx+1}/{self.total_to_dl}]: {new_fname}{size_mb_str}...")
                    
                    self.file_progress_bar.set(0)
                    self.file_start_time = time.time()
                    success = self._download_file(v_url, local_path)
                    
                    if success:
                        dl_time = time.time() - self.file_start_time
                        downloaded_count += 1
                        self.log(f"    ✅ Saved: {local_path}{size_mb_str} (Took {dl_time:.1f}s)")
                        
                        sync_history[orig_fname] = {
                            "remote_size": remote_size,
                            "local_filename": new_fname
                        }
                        try:
                            with open(history_path, 'w', encoding='utf-8') as f:
                                json.dump(sync_history, f, indent=4)
                        except Exception as e:
                            self.log(f"    ⚠️ Could not save history: {e}")

                        if self.convert_h264.get() and local_path.lower().endswith(('.mp4', '.mov')):
                            self.log(f"    ⏳ Converting to H.264: {new_fname}...")
                            self.update_status(f"Converting {new_fname}...", "#F59E0B")
                            self.file_progress_lbl.configure(text=f"Current File Progress: Converting H.264...")
                            self.file_progress_bar.set(0)
                            self.file_start_time = time.time()
                            new_path = self._convert_to_h264(local_path)
                            if new_path:
                                conv_time = time.time() - self.file_start_time
                                self.log(f"    ✅ Converted: {os.path.basename(new_path)} (Took {conv_time:.1f}s)")
                                if self.delete_original.get():
                                    try:
                                        os.remove(local_path)
                                        self.log(f"    🗑️ Deleted original: {new_fname}")
                                    except Exception as e:
                                        self.log(f"    ⚠️ Could not delete original: {e}")
                            else:
                                self.log(f"    ❌ Conversion failed. Check the log above for details.")

                        if self.delete_from_vrx.get():
                            self.log(f"    🗑️ Auto-deleting from VRX SD card: {orig_fname}...")
                            try:
                                del_url = f"{url_base}delete/{urllib.parse.quote(orig_fname)}"
                                urllib.request.urlopen(del_url, timeout=5)
                                self.log(f"    ✅ Erased from VRX SD card: {orig_fname}")
                            except Exception as e:
                                self.log(f"    ⚠️ Could not erase from VRX SD card: {e}")
                    else:
                        if self.stop_requested:
                            self.log(f"    ⛔ Download cancelled: {new_fname}")
                        else:
                            self.log(f"    ❌ Download failed: {new_fname}")

                    self.progress_bar.set((idx + 1) / self.total_to_dl)
                    self.eta_lbl.configure(text="")

                if self.stop_requested:
                    self.log(f"\n[!] Sync Aborted. Downloaded {downloaded_count} file(s) before abort.")
                    self.update_status("Sync Aborted", "#EF4444")
                    self.job_progress_lbl.configure(text=f"Overall Job Progress: Aborted ({downloaded_count}/{self.total_to_dl} files)")
                    self.file_progress_lbl.configure(text="Current File Progress: Idle")
                else:
                    self.log(f"\n[🎉] Download Complete! ({downloaded_count}/{self.total_to_dl} files downloaded)")
                    show_os_toast("OpenIPC VRX Sync", f"Downloaded {downloaded_count} new flight video(s)!")
                    self.job_progress_lbl.configure(text=f"Overall Job Progress: Completed ({downloaded_count}/{self.total_to_dl} files, 100%)")
                    self.file_progress_lbl.configure(text="Current File Progress: Idle")

            if not skip_wifi and self.auto_reconnect.get() and home_ssid:
                self.update_status(f"Reconnecting to Home Wi-Fi ({home_ssid})...", "#F59E0B")
                self.log(f"[*] Reconnecting Wi-Fi back to Home network '{home_ssid}'...")
                connect_to_wifi(home_ssid)
                self.log("[+] Reconnect command sent.")

            if not self.stop_requested:
                self.update_status("Sync Complete!", "#10B981")

        except Exception as e:
            self.log(f"[X] Unexpected Error: {e}")
            self.update_status("Error occurred", "#EF4444")
        finally:
            self.is_running = False
            self.stop_requested = False
            self.start_btn.configure(state="normal")
            self.quick_download_btn.configure(state="normal")
            self.manage_vrx_btn.configure(state="normal")
            self.abort_btn.configure(state="disabled")

    def _convert_to_h264(self, input_path):
        base, ext = os.path.splitext(input_path)
        output_path = f"{base}_h264{ext}"
        try:
            cmd = ["ffmpeg", "-y", "-i", input_path, "-c:v", "libx264", "-crf", "23", "-preset", "fast", "-c:a", "copy", output_path]
            creation_flags = subprocess.CREATE_NO_WINDOW if OS_NAME == "Windows" else 0
            
            process = subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, text=True, creationflags=creation_flags)
            duration_secs = 0.0
            
            last_errors = []
            for line in process.stderr:
                last_errors.append(line.strip())
                if len(last_errors) > 10:
                    last_errors.pop(0)

                if self.stop_requested:
                    process.terminate()
                    break
                if "Duration:" in line and duration_secs == 0:
                    match = re.search(r"Duration:\s*(\d+):(\d+):(\d+\.\d+)", line)
                    if match:
                        h, m, s = match.groups()
                        duration_secs = int(h)*3600 + int(m)*60 + float(s)
                elif "time=" in line and duration_secs > 0:
                    match = re.search(r"time=(\d+):(\d+):(\d+\.\d+)", line)
                    if match:
                        h, m, s = match.groups()
                        current_secs = int(h)*3600 + int(m)*60 + float(s)
                        prog = current_secs / duration_secs
                        self.file_progress_bar.set(min(prog, 1.0))
                        
                        if time.time() - self._last_eta_update > 0.5:
                            self._update_eta(prog)
                            self._last_eta_update = time.time()
                        
            process.wait()
            
            if process.returncode == 0 and os.path.exists(output_path):
                self.file_progress_bar.set(1.0)
                return output_path
            else:
                err_out = " | ".join(last_errors[-3:]) if last_errors else "Unknown Error"
                self.log(f"    [!] FFmpeg returned an error (code {process.returncode}): {err_out}")
                return None
        except FileNotFoundError:
            self.log("    [!] FileNotFoundError: 'ffmpeg' command not found. Please ensure FFmpeg is installed AND added to your system PATH.")
            return None
        except Exception as e:
            self.log(f"    [!] Conversion exception: {e}")
            return None

    def _scan_vrx_directory(self, base_url, visited=None):
        if visited is None:
            visited = set()

        if base_url in visited or self.stop_requested:
            return []
        visited.add(base_url)

        video_urls = []
        try:
            req = urllib.request.urlopen(base_url, timeout=5)
            html_content = req.read().decode('utf-8', errors='ignore')

            parser = HTMLDirectoryParser()
            parser.feed(html_content)

            for link in parser.links:
                if self.stop_requested:
                    break
                if link in ('../', './', '/') or link.startswith('?') or link.startswith('http'):
                    continue

                full_url = urllib.parse.urljoin(base_url, link)
                
                if link.endswith('/'):
                    video_urls.extend(self._scan_vrx_directory(full_url, visited))
                elif link.lower().endswith(VIDEO_EXTENSIONS):
                    video_urls.append(full_url)
        except Exception as e:
            self.log(f"[!] Warning reading {base_url}: {e}")

        return video_urls

    def _download_file(self, url, dest_path):
        try:
            req = urllib.request.urlopen(url, timeout=10)
            file_size = int(req.headers.get('Content-Length', 0))

            chunk_size = 1024 * 256 # 256KB chunks
            bytes_dl = 0

            with open(dest_path + ".tmp", "wb") as f:
                while True:
                    if self.stop_requested:
                        break
                    chunk = req.read(chunk_size)
                    if not chunk:
                        break
                    f.write(chunk)
                    bytes_dl += len(chunk)
                    if file_size > 0:
                        prog = bytes_dl / file_size
                        self.file_progress_bar.set(min(prog, 1.0))
                        
                        if time.time() - self._last_eta_update > 0.25:
                            mb_dl = bytes_dl / (1024 * 1024)
                            mb_tot = file_size / (1024 * 1024)
                            pct = int(prog * 100)
                            self.file_progress_lbl.configure(text=f"Current File Progress: {mb_dl:.1f} MB / {mb_tot:.1f} MB ({pct}%)")
                            
                            elapsed = time.time() - self.file_start_time
                            speed = bytes_dl / elapsed if elapsed > 0 else 0
                            self._update_eta(prog, speed_text=self._format_speed(speed))
                            self._last_eta_update = time.time()

            if self.stop_requested:
                if os.path.exists(dest_path + ".tmp"):
                    os.remove(dest_path + ".tmp")
                return False

            if os.path.exists(dest_path):
                os.remove(dest_path)
            os.rename(dest_path + ".tmp", dest_path)
            return True
        except Exception as e:
            if os.path.exists(dest_path + ".tmp"):
                os.remove(dest_path + ".tmp")
            return False

    def destroy(self):
        self.monitor_active = False
        super().destroy()

if __name__ == "__main__":
    app = OpenIPCFlightDownloader()
    app.mainloop()

