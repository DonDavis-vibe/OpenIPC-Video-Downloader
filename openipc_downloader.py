import os
import sys
import time
import re
import threading
import subprocess
import platform
import urllib.request
import urllib.parse
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

        self.is_running = False
        self.stop_requested = False

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

        # Options
        options_frame = ctk.CTkFrame(config_frame, fg_color="transparent")
        options_frame.grid(row=3, column=0, columnspan=4, sticky="w", padx=12, pady=(4, 10))
        
        reconnect_chk = ctk.CTkCheckBox(options_frame, text="Auto-reconnect to Home Wi-Fi", variable=self.auto_reconnect)
        reconnect_chk.pack(side="left", padx=(0, 20))
        
        convert_chk = ctk.CTkCheckBox(options_frame, text="Auto-convert H.265 to H.264 (Requires FFmpeg)", variable=self.convert_h264)
        convert_chk.pack(side="left")

        delete_chk = ctk.CTkCheckBox(options_frame, text="Delete original after conversion", variable=self.delete_original)
        delete_chk.pack(side="left", padx=(20, 0))

        # Bottom Action Buttons Frame (Packed FIRST at bottom!)
        btn_frame = ctk.CTkFrame(self, fg_color="transparent")
        btn_frame.pack(side="bottom", fill="x", padx=15, pady=(6, 12))

        self.start_btn = ctk.CTkButton(btn_frame, text="⚡ Start Sync & Download", font=ctk.CTkFont(size=14, weight="bold"),
                                        fg_color="#10B981", hover_color="#059669", height=44, command=self.start_sync_thread)
        self.start_btn.pack(side="left", fill="x", expand=True, padx=(0, 4))

        self.quick_download_btn = ctk.CTkButton(btn_frame, text="📥 Download Only", font=ctk.CTkFont(size=12),
                                                fg_color="#4F46E5", hover_color="#4338CA", height=44, command=lambda: self.start_sync_thread(skip_wifi=True))
        self.quick_download_btn.pack(side="left", fill="x", expand=True, padx=4)

        # Abort Button (Initially Disabled)
        self.abort_btn = ctk.CTkButton(btn_frame, text="⛔ Abort Sync", font=ctk.CTkFont(size=13, weight="bold"),
                                        fg_color="#EF4444", hover_color="#DC2626", height=44, state="disabled", command=self.request_abort)
        self.abort_btn.pack(side="right", fill="x", expand=True, padx=(4, 0))

        # Status & Progress Frame (Takes remaining space)
        status_frame = ctk.CTkFrame(self, corner_radius=10)
        status_frame.pack(side="top", fill="both", expand=True, padx=15, pady=6)

        self.status_lbl = ctk.CTkLabel(status_frame, text="Status: Ready", font=ctk.CTkFont(size=13, weight="bold"), text_color="#3B82F6")
        self.status_lbl.pack(anchor="w", padx=12, pady=(8, 4))

        self.progress_bar = ctk.CTkProgressBar(status_frame)
        self.progress_bar.pack(fill="x", padx=12, pady=4)
        self.progress_bar.set(0)

        self.file_progress_bar = ctk.CTkProgressBar(status_frame, progress_color="#10B981")
        self.file_progress_bar.pack(fill="x", padx=12, pady=4)
        self.file_progress_bar.set(0)

        self.log_textbox = ctk.CTkTextbox(status_frame, font=ctk.CTkFont(family="Consolas", size=11))
        self.log_textbox.pack(fill="both", expand=True, padx=12, pady=(4, 8))

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
                    self.log(f"[!] Warning: Wi-Fi status did not report '{vrx_ssid}', attempting HTTP reachability check anyway...")

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
                    local_path = os.path.join(target_dir, fname)
                    
                    if os.path.exists(local_path):
                        try:
                            req = urllib.request.Request(v_url, method='HEAD')
                            with urllib.request.urlopen(req, timeout=3) as resp:
                                remote_size = int(resp.headers.get('Content-Length', 0))
                                local_size = os.path.getsize(local_path)
                                if remote_size > 0 and remote_size == local_size:
                                    self.log(f"[-] Skipping already downloaded: {fname}")
                                    continue
                        except Exception:
                            self.log(f"[-] Local file exists: {fname} (Skipping)")
                            continue
                    to_download.append((v_url, fname, local_path))

                if self.stop_requested:
                    self.log("[!] Sync aborted by user.")
                    self.update_status("Sync Aborted", "#EF4444")
                    return

                self.log(f"[*] {len(to_download)} new video(s) ready for download.")

                downloaded_count = 0
                total_to_dl = len(to_download)

                for idx, (v_url, fname, local_path) in enumerate(to_download):
                    if self.stop_requested:
                        self.log("[!] Download loop aborted by user.")
                        break

                    self.update_status(f"Downloading {idx+1}/{total_to_dl}: {fname}", "#10B981")
                    self.log(f"[*] Downloading [{idx+1}/{total_to_dl}]: {fname}...")
                    
                    self.file_progress_bar.set(0)
                    start_time = time.time()
                    success = self._download_file(v_url, local_path)
                    
                    if success:
                        dl_time = time.time() - start_time
                        downloaded_count += 1
                        self.log(f"    ✅ Saved: {local_path} (Took {dl_time:.1f}s)")
                        if self.convert_h264.get() and local_path.lower().endswith(('.mp4', '.mov')):
                            self.log(f"    ⏳ Converting to H.264: {fname}...")
                            self.update_status(f"Converting {fname}...", "#F59E0B")
                            self.file_progress_bar.set(0)
                            conv_start = time.time()
                            new_path = self._convert_to_h264(local_path)
                            if new_path:
                                conv_time = time.time() - conv_start
                                self.log(f"    ✅ Converted: {os.path.basename(new_path)} (Took {conv_time:.1f}s)")
                                if self.delete_original.get():
                                    try:
                                        os.remove(local_path)
                                        self.log(f"    🗑️ Deleted original: {fname}")
                                    except Exception as e:
                                        self.log(f"    ⚠️ Could not delete original: {e}")
                            else:
                                self.log(f"    ❌ Conversion failed (Is FFmpeg installed?)")
                    else:
                        if self.stop_requested:
                            self.log(f"    ⛔ Download cancelled: {fname}")
                        else:
                            self.log(f"    ❌ Download failed: {fname}")

                    self.progress_bar.set((idx + 1) / total_to_dl)

                if self.stop_requested:
                    self.log(f"\n[!] Sync Aborted. Downloaded {downloaded_count} file(s) before abort.")
                    self.update_status("Sync Aborted", "#EF4444")
                else:
                    self.log(f"\n[🎉] Download Complete! ({downloaded_count}/{total_to_dl} files downloaded)")
                    show_os_toast("OpenIPC VRX Sync", f"Downloaded {downloaded_count} new flight video(s)!")

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
            self.abort_btn.configure(state="disabled")

    def _convert_to_h264(self, input_path):
        base, ext = os.path.splitext(input_path)
        output_path = f"{base}_h264{ext}"
        try:
            cmd = ["ffmpeg", "-y", "-i", input_path, "-c:v", "libx264", "-crf", "23", "-preset", "fast", "-c:a", "copy", output_path]
            creation_flags = subprocess.CREATE_NO_WINDOW if OS_NAME == "Windows" else 0
            
            process = subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, text=True, creationflags=creation_flags)
            duration_secs = 0.0
            
            for line in process.stderr:
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
                        
            process.wait()
            
            if process.returncode == 0 and os.path.exists(output_path):
                self.file_progress_bar.set(1.0)
                return output_path
            else:
                self.log(f"    [!] FFmpeg Error. Ensure ffmpeg is in your system PATH.")
                return None
        except FileNotFoundError:
            return None
        except Exception as e:
            self.log(f"    [!] Conversion error: {e}")
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
