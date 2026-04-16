import os
import sys
import threading
from pathlib import Path
from datetime import timedelta
import tkinter as tk
from tkinter import messagebox, filedialog

import customtkinter as ctk
import yt_dlp
from PIL import Image, ImageTk
import requests
from io import BytesIO

def get_resource_path(relative_path):
    try:
        base_path = sys._MEIPASS
    except Exception:
        base_path = os.path.abspath(".")
    return os.path.join(base_path, relative_path)

# ======================== CONFIGURATION ========================
ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("blue")

APP_NAME = "YouTube Downloader Pro"
APP_VERSION = "1.0.0"
WATERMARK_TEXT = "Made by RaulRDA | www.raulrda.com"
ICON_FILE = "ydp-icon.ico"
ICON_PNG = "ydp-icon.png"
BUTTON_ICON = "ydp-icon-white.png"

# ======================== CORE DOWNLOADER ========================
class YoutubeDownloader:
    def __init__(self, output_dir=None):
        self.output_dir = output_dir or str(Path.home() / "Downloads")
        self.progress_hook = None
        self.last_info = None
        self.is_downloading = False
        self.cancel_requested = False

    def set_progress_hook(self, hook_func):
        self.progress_hook = hook_func

    def _progress_hook_wrapper(self, d):
        if self.cancel_requested:
            raise Exception("Download cancelled by user")
        if self.progress_hook:
            self.progress_hook(d)

    def get_video_info(self, url):
        ydl_opts = {'quiet': True, 'no_warnings': True, 'extract_flat': False}
        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(url, download=False)
                self.last_info = info
                return info
        except Exception as e:
            raise RuntimeError(f"Error fetching info: {str(e)}")

    def search_videos(self, query, max_results=5):
        ydl_opts = {
            'quiet': True,
            'no_warnings': True,
            'extract_flat': 'in_playlist',
            'default_search': 'ytsearch',
        }
        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                search_query = f"ytsearch{max_results}:{query}"
                info = ydl.extract_info(search_query, download=False)
                entries = info.get('entries', [])
                results = []
                for entry in entries:
                    results.append({
                        'title': entry.get('title', 'No title'),
                        'url': entry.get('webpage_url') or f"https://youtube.com/watch?v={entry.get('id')}",
                        'duration': entry.get('duration', 0),
                        'uploader': entry.get('uploader', 'Unknown'),
                        'thumbnail': entry.get('thumbnail', ''),
                    })
                return results
        except Exception as e:
            raise RuntimeError(f"Search error: {str(e)}")

    def _get_format_string(self, format_type, quality):
        if format_type == 'mp3':
            return 'bestaudio/best'
        else:
            quality_map = {
                'Best': 'best',
                '2160p': 'bestvideo[height<=2160]+bestaudio/best[height<=2160]',
                '1440p': 'bestvideo[height<=1440]+bestaudio/best[height<=1440]',
                '1080p': 'bestvideo[height<=1080]+bestaudio/best[height<=1080]',
                '720p':  'bestvideo[height<=720]+bestaudio/best[height<=720]',
                '480p':  'bestvideo[height<=480]+bestaudio/best[height<=480]',
                '360p':  'bestvideo[height<=360]+bestaudio/best[height<=360]',
                '240p':  'bestvideo[height<=240]+bestaudio/best[height<=240]',
                '144p':  'bestvideo[height<=144]+bestaudio/best[height<=144]',
            }
            return quality_map.get(quality, 'best')

    def download(self, url, format_type='mp4', quality='1080p', output_dir=None):
        self.is_downloading = True
        self.cancel_requested = False
        out_dir = output_dir or self.output_dir
        os.makedirs(out_dir, exist_ok=True)

        outtmpl = os.path.join(out_dir, '%(title)s.%(ext)s')
        ydl_opts = {
            'format': self._get_format_string(format_type, quality),
            'outtmpl': outtmpl,
            'progress_hooks': [self._progress_hook_wrapper],
            'quiet': True,
            'no_warnings': True,
            'ignoreerrors': True,
        }

        if format_type == 'mp3':
            ydl_opts['postprocessors'] = [{
                'key': 'FFmpegExtractAudio',
                'preferredcodec': 'mp3',
                'preferredquality': quality.replace('k', '') if quality.endswith('k') else '192',
            }]
            ydl_opts['extractaudio'] = True
            ydl_opts['audioformat'] = 'mp3'

        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                ydl.download([url])
            self.is_downloading = False
            return True, "Download completed"
        except Exception as e:
            self.is_downloading = False
            if self.cancel_requested:
                return False, "Download cancelled"
            return False, str(e)

    def cancel(self):
        self.cancel_requested = True


# ======================== GUI ========================
class YTDLoader(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title(APP_NAME)
        self.geometry("880x620")
        self.minsize(800, 550)

        # Set window icon
        try:
            icon_path = get_resource_path(ICON_FILE)
            if os.path.exists(icon_path):
                self.iconbitmap(icon_path)
            elif os.path.exists(get_resource_path(ICON_PNG)):
                img = Image.open(get_resource_path(ICON_PNG))
                photo = ImageTk.PhotoImage(img)
                self.iconphoto(True, photo)
        except:
            pass

        self.downloader = YoutubeDownloader()
        self.current_info = None
        self.search_results = []
        self.thumbnail_image = None
        self.button_icon_img = None

        self.downloader.set_progress_hook(self.progress_hook)
        self.create_widgets()
        self.protocol("WM_DELETE_WINDOW", self.on_closing)

        self.after(2000, self.check_for_updates)

    def check_for_updates(self):
        """Check GitHub for new releases in background."""
        try:
            import urllib.request
            import json

            # Get latest release info from GitHub API
            url = "https://api.github.com/repos/RaulRDA/YouTubeDownloaderPro/releases/latest"
            req = urllib.request.Request(url, headers={"User-Agent": "YouTubeDownloaderPro"})

            with urllib.request.urlopen(req, timeout=5) as response:
                data = json.loads(response.read().decode())
                latest_version = data.get("tag_name", "").lstrip("v")
                download_url = data.get("html_url", "")

            # Compare with current version
            if latest_version and latest_version > APP_VERSION:
                self.after(0, lambda: self.show_update_notification(latest_version, download_url))
        except Exception as e:
            print(f"Update check failed: {e}")

    def show_update_notification(self, version, url):
        """Show a non-intrusive update notification."""
        notification = ctk.CTkToplevel(self)
        notification.title("Update Available")
        notification.geometry("400x180")
        notification.resizable(False, False)
        notification.transient(self)
        notification.grab_set()

        notification.update_idletasks()
        x = self.winfo_x() + (self.winfo_width() // 2) - (400 // 2)
        y = self.winfo_y() + (self.winfo_height() // 2) - (180 // 2)
        notification.geometry(f"+{x}+{y}")

        ctk.CTkLabel(notification, text="🆕 New version available!", font=ctk.CTkFont(size=16, weight="bold")).pack(pady=(20, 5))
        ctk.CTkLabel(notification, text=f"Version {version} is ready to download", font=ctk.CTkFont(size=12)).pack()
        ctk.CTkLabel(notification, text="You're using an older version.", font=ctk.CTkFont(size=12)).pack()

        btn_frame = ctk.CTkFrame(notification, fg_color="transparent")
        btn_frame.pack(pady=20)

        def open_download():
            import webbrowser
            webbrowser.open(url)
            notification.destroy()

        def remind_later():
            notification.destroy()

        ctk.CTkButton(btn_frame, text="Download Now", command=open_download, width=120, corner_radius=8).pack(side="left", padx=5)
        ctk.CTkButton(btn_frame, text="Remind Later", command=remind_later, width=120, corner_radius=8, fg_color="gray").pack(side="left", padx=5)

    def create_widgets(self):
        # Main scrollable frame
        self.main_frame = ctk.CTkScrollableFrame(self, fg_color="transparent")
        self.main_frame.pack(fill="both", expand=True, padx=15, pady=15)
        self.main_frame.grid_columnconfigure(0, weight=1)

        # ----- Top: URL / Search -----
        input_frame = ctk.CTkFrame(self.main_frame, corner_radius=12)
        input_frame.grid(row=0, column=0, sticky="ew", pady=(0, 12))
        input_frame.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(input_frame, text="Video URL or search:", font=ctk.CTkFont(size=13, weight="bold")).grid(row=0, column=0, sticky="w", padx=12, pady=(8, 0))
        self.url_entry = ctk.CTkEntry(input_frame, placeholder_text="https://youtube.com/... or search term", height=38, corner_radius=8)
        self.url_entry.grid(row=1, column=0, sticky="ew", padx=12, pady=(5, 8))

        btn_row = ctk.CTkFrame(input_frame, fg_color="transparent")
        btn_row.grid(row=2, column=0, sticky="ew", padx=12, pady=(0, 10))
        btn_row.grid_columnconfigure(0, weight=1)
        btn_row.grid_columnconfigure(1, weight=1)

        self.fetch_btn = ctk.CTkButton(btn_row, text="🔍 Get Info", command=self.fetch_info_thread, height=36, corner_radius=8)
        self.fetch_btn.grid(row=0, column=0, padx=(0, 5), sticky="ew")
        self.search_btn = ctk.CTkButton(btn_row, text="📋 Search", command=self.search_thread, height=36, corner_radius=8, fg_color="#2c6e2c", hover_color="#1e4f1e")
        self.search_btn.grid(row=0, column=1, padx=(5, 0), sticky="ew")

        # ----- Search results listbox (compact) -----
        search_frame = ctk.CTkFrame(self.main_frame, corner_radius=12)
        search_frame.grid(row=1, column=0, sticky="ew", pady=(0, 12))
        search_frame.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(search_frame, text="Search results:", font=ctk.CTkFont(size=13, weight="bold")).grid(row=0, column=0, sticky="w", padx=12, pady=(8, 0))
        self.search_listbox = tk.Listbox(search_frame, height=4, bg="#2b2b2b", fg="white", selectbackground="#1f538d", font=("Segoe UI", 10), relief="flat", highlightthickness=0)
        self.search_listbox.grid(row=1, column=0, sticky="ew", padx=12, pady=(5, 10))
        scrollbar = ctk.CTkScrollbar(search_frame, command=self.search_listbox.yview)
        scrollbar.grid(row=1, column=1, sticky="ns", pady=(5, 10))
        self.search_listbox.config(yscrollcommand=scrollbar.set)
        self.search_listbox.bind('<<ListboxSelect>>', self.on_search_select)

        # ----- Video info with thumbnail -----
        info_frame = ctk.CTkFrame(self.main_frame, corner_radius=12)
        info_frame.grid(row=2, column=0, sticky="ew", pady=(0, 12))
        info_frame.grid_columnconfigure(0, weight=0)  # thumbnail
        info_frame.grid_columnconfigure(1, weight=1)

        self.thumbnail_label = ctk.CTkLabel(info_frame, text="Thumbnail", width=160, height=90, fg_color="#1e1e1e", corner_radius=8)
        self.thumbnail_label.grid(row=0, column=0, padx=12, pady=12, sticky="n")

        info_text = ctk.CTkFrame(info_frame, fg_color="transparent")
        info_text.grid(row=0, column=1, sticky="nsew", padx=(0, 12), pady=12)
        info_text.grid_columnconfigure(0, weight=1)

        self.title_label = ctk.CTkLabel(info_text, text="Title: ---", font=ctk.CTkFont(size=13, weight="bold"), wraplength=500, justify="left")
        self.title_label.grid(row=0, column=0, sticky="w", pady=(0, 4))
        self.duration_label = ctk.CTkLabel(info_text, text="Duration: ---", font=ctk.CTkFont(size=11))
        self.duration_label.grid(row=1, column=0, sticky="w")
        self.uploader_label = ctk.CTkLabel(info_text, text="Channel: ---", font=ctk.CTkFont(size=11))
        self.uploader_label.grid(row=2, column=0, sticky="w")
        self.views_label = ctk.CTkLabel(info_text, text="Views: ---", font=ctk.CTkFont(size=11))
        self.views_label.grid(row=3, column=0, sticky="w")

        # ----- Download options -----
        opts_frame = ctk.CTkFrame(self.main_frame, corner_radius=12)
        opts_frame.grid(row=3, column=0, sticky="ew", pady=(0, 12))
        opts_frame.grid_columnconfigure(0, weight=0)
        opts_frame.grid_columnconfigure(1, weight=1)
        opts_frame.grid_columnconfigure(2, weight=0)

        ctk.CTkLabel(opts_frame, text="Format:", font=ctk.CTkFont(size=12)).grid(row=0, column=0, padx=(12, 5), pady=12, sticky="w")
        self.format_var = ctk.StringVar(value="mp4")
        format_switch = ctk.CTkSegmentedButton(opts_frame, values=["mp4", "mp3"], variable=self.format_var, command=self.on_format_change, width=100)
        format_switch.grid(row=0, column=1, padx=5, pady=12, sticky="w")

        ctk.CTkLabel(opts_frame, text="Quality:", font=ctk.CTkFont(size=12)).grid(row=1, column=0, padx=(12, 5), pady=(0, 12), sticky="w")
        self.quality_combo = ctk.CTkComboBox(opts_frame, values=[], state="readonly", width=120, corner_radius=8)
        self.quality_combo.grid(row=1, column=1, padx=5, pady=(0, 12), sticky="w")

        # Output folder
        ctk.CTkLabel(opts_frame, text="Save to:", font=ctk.CTkFont(size=12)).grid(row=2, column=0, padx=(12, 5), pady=(0, 12), sticky="w")
        dir_frame = ctk.CTkFrame(opts_frame, fg_color="transparent")
        dir_frame.grid(row=2, column=1, padx=5, pady=(0, 12), sticky="ew")
        dir_frame.grid_columnconfigure(0, weight=1)
        self.dir_var = ctk.StringVar(value=str(Path.home() / "Downloads"))
        dir_entry = ctk.CTkEntry(dir_frame, textvariable=self.dir_var, corner_radius=8, height=32)
        dir_entry.grid(row=0, column=0, sticky="ew", padx=(0, 8))
        browse_btn = ctk.CTkButton(dir_frame, text="📁", width=40, height=32, command=self.browse_folder, corner_radius=8)
        browse_btn.grid(row=0, column=1)

        # ----- Progress bar and download button -----
        progress_frame = ctk.CTkFrame(self.main_frame, corner_radius=12)
        progress_frame.grid(row=4, column=0, sticky="ew", pady=(0, 12))
        progress_frame.grid_columnconfigure(0, weight=1)

        self.progress_bar = ctk.CTkProgressBar(progress_frame, height=10, corner_radius=5)
        self.progress_bar.grid(row=0, column=0, padx=12, pady=(12, 5), sticky="ew")
        self.progress_bar.set(0)

        self.status_label = ctk.CTkLabel(progress_frame, text="Ready", font=ctk.CTkFont(size=11))
        self.status_label.grid(row=1, column=0, padx=12, pady=(0, 8))

        # Button row with icon
        btn_row2 = ctk.CTkFrame(progress_frame, fg_color="transparent")
        btn_row2.grid(row=2, column=0, padx=12, pady=(0, 12))
        btn_row2.grid_columnconfigure(0, weight=1)
        btn_row2.grid_columnconfigure(1, weight=1)

        # Load button icon
        self.button_icon_img = self.load_button_icon()
        if self.button_icon_img:
            self.download_btn = ctk.CTkButton(btn_row2, text=" Download", image=self.button_icon_img, compound="left", command=self.download_thread, height=40, corner_radius=10, font=ctk.CTkFont(size=13, weight="bold"))
        else:
            self.download_btn = ctk.CTkButton(btn_row2, text="⬇️ Download", command=self.download_thread, height=40, corner_radius=10, font=ctk.CTkFont(size=13, weight="bold"))
        self.download_btn.grid(row=0, column=0, padx=(0, 5), sticky="ew")

        self.cancel_btn = ctk.CTkButton(btn_row2, text="❌ Cancel", command=self.cancel_download, height=40, corner_radius=10, fg_color="#a83232", hover_color="#7a2525", state="disabled")
        self.cancel_btn.grid(row=0, column=1, padx=(5, 0), sticky="ew")

        # ----- Watermark -----
        watermark = ctk.CTkLabel(self.main_frame, text=WATERMARK_TEXT, font=ctk.CTkFont(size=10, slant="italic"), text_color="gray")
        watermark.grid(row=5, column=0, pady=(5, 0))

        # Initialize quality options
        self.on_format_change()

    def load_button_icon(self):
        """Load button icon from ydp-icon-white.png if exists."""
        icon_path = get_resource_path(BUTTON_ICON)
        if os.path.exists(icon_path):
            try:
                img = Image.open(icon_path)
                img = img.resize((20, 20), Image.LANCZOS)
                return ctk.CTkImage(light_image=img, dark_image=img, size=(20, 20))
            except:
                return None
        return None

    def on_format_change(self, choice=None):
        fmt = self.format_var.get()
        if fmt == "mp4":
            qualities = ['Best', '2160p', '1440p', '1080p', '720p', '480p', '360p', '240p', '144p']
            self.quality_combo.configure(values=qualities)
            self.quality_combo.set('1080p')
        else:
            qualities = ['320k', '192k', '128k']
            self.quality_combo.configure(values=qualities)
            self.quality_combo.set('192k')

    def browse_folder(self):
        folder = filedialog.askdirectory(initialdir=self.dir_var.get())
        if folder:
            self.dir_var.set(folder)

    # ----- Fetch info thread -----
    def fetch_info_thread(self):
        url = self.url_entry.get().strip()
        if not url:
            messagebox.showerror("Error", "Enter a YouTube URL")
            return
        self.fetch_btn.configure(state="disabled")
        self.search_btn.configure(state="disabled")
        self.status_label.configure(text="Fetching info...", text_color="yellow")
        threading.Thread(target=self.fetch_info, args=(url,), daemon=True).start()

    def fetch_info(self, url):
        try:
            info = self.downloader.get_video_info(url)
            self.current_info = info
            self.after(0, self.display_info, info)
            self.after(0, lambda: self.status_label.configure(text="Info loaded", text_color="green"))
        except Exception as e:
            self.after(0, lambda: messagebox.showerror("Error", str(e)))
            self.after(0, lambda: self.status_label.configure(text="Error", text_color="red"))
        finally:
            self.after(0, lambda: self.fetch_btn.configure(state="normal"))
            self.after(0, lambda: self.search_btn.configure(state="normal"))

    def display_info(self, info):
        title = info.get('title', 'Unknown')
        duration = info.get('duration', 0)
        uploader = info.get('uploader', 'Unknown')
        views = info.get('view_count', 'N/A')
        if views != 'N/A':
            views = f"{views:,}"
        duration_str = str(timedelta(seconds=duration)) if duration else 'Unknown'

        self.title_label.configure(text=f"Title: {title}")
        self.duration_label.configure(text=f"Duration: {duration_str}")
        self.uploader_label.configure(text=f"Channel: {uploader}")
        self.views_label.configure(text=f"Views: {views}")

        thumbnail_url = info.get('thumbnail', '')
        if thumbnail_url:
            self.load_thumbnail(thumbnail_url)

    def load_thumbnail(self, url):
        def _load():
            try:
                response = requests.get(url, timeout=10)
                img_data = response.content
                img = Image.open(BytesIO(img_data))
                img = img.resize((160, 90), Image.LANCZOS)
                ctk_img = ctk.CTkImage(light_image=img, dark_image=img, size=(160, 90))
                self.after(0, lambda: self.thumbnail_label.configure(image=ctk_img, text=""))
                self.thumbnail_image = ctk_img
            except:
                self.after(0, lambda: self.thumbnail_label.configure(text="No thumbnail"))
        threading.Thread(target=_load, daemon=True).start()

    # ----- Search -----
    def search_thread(self):
        query = self.url_entry.get().strip()
        if not query:
            messagebox.showerror("Error", "Enter a search term")
            return
        self.search_btn.configure(state="disabled")
        self.fetch_btn.configure(state="disabled")
        self.status_label.configure(text="Searching...", text_color="yellow")
        threading.Thread(target=self.search_videos, args=(query,), daemon=True).start()

    def search_videos(self, query):
        try:
            results = self.downloader.search_videos(query, max_results=8)
            self.search_results = results
            self.after(0, self.update_search_listbox)
            self.after(0, lambda: self.status_label.configure(text=f"Found {len(results)} results", text_color="green"))
        except Exception as e:
            self.after(0, lambda: messagebox.showerror("Error", str(e)))
            self.after(0, lambda: self.status_label.configure(text="Search error", text_color="red"))
        finally:
            self.after(0, lambda: self.search_btn.configure(state="normal"))
            self.after(0, lambda: self.fetch_btn.configure(state="normal"))

    def update_search_listbox(self):
        self.search_listbox.delete(0, tk.END)
        for res in self.search_results:
            title = res['title']
            duration = res.get('duration', 0)
            duration_str = f"[{str(timedelta(seconds=duration))}]" if duration else ""
            self.search_listbox.insert(tk.END, f"{title} {duration_str}")

    def on_search_select(self, event):
        selection = self.search_listbox.curselection()
        if not selection:
            return
        idx = selection[0]
        if 0 <= idx < len(self.search_results):
            video = self.search_results[idx]
            self.url_entry.delete(0, tk.END)
            self.url_entry.insert(0, video['url'])
            self.fetch_info_thread()

    # ----- Download -----
    def download_thread(self):
        if self.downloader.is_downloading:
            messagebox.showinfo("Info", "Download already in progress")
            return
        url = self.url_entry.get().strip()
        if not url:
            messagebox.showerror("Error", "No URL to download")
            return
        fmt = self.format_var.get()
        quality = self.quality_combo.get()
        output_dir = self.dir_var.get()

        self.download_btn.configure(state="disabled")
        self.cancel_btn.configure(state="normal")
        self.fetch_btn.configure(state="disabled")
        self.search_btn.configure(state="disabled")
        self.progress_bar.set(0)
        self.status_label.configure(text="Starting download...", text_color="yellow")

        def run():
            success, msg = self.downloader.download(url, fmt, quality, output_dir)
            self.after(0, self.download_finished, success, msg)

        threading.Thread(target=run, daemon=True).start()

    def progress_hook(self, d):
        if d['status'] == 'downloading':
            total = d.get('total_bytes', 0) or d.get('total_bytes_estimate', 0)
            downloaded = d.get('downloaded_bytes', 0)
            if total > 0:
                percent = (downloaded / total) * 100
                self.after(0, lambda p=percent: self.progress_bar.set(p/100))
                self.after(0, lambda p=percent: self.status_label.configure(text=f"Downloading... {p:.1f}%", text_color="cyan"))
        elif d['status'] == 'finished':
            self.after(0, lambda: self.status_label.configure(text="Processing...", text_color="orange"))

    def download_finished(self, success, msg):
        self.download_btn.configure(state="normal")
        self.cancel_btn.configure(state="disabled")
        self.fetch_btn.configure(state="normal")
        self.search_btn.configure(state="normal")
        if success:
            messagebox.showinfo("Success", msg)
            self.progress_bar.set(0)
            self.status_label.configure(text="Download completed", text_color="green")
        else:
            messagebox.showerror("Error", msg)
            self.status_label.configure(text="Download error", text_color="red")

    def cancel_download(self):
        if self.downloader.is_downloading:
            self.downloader.cancel()
            self.status_label.configure(text="Cancelling...", text_color="red")
            self.cancel_btn.configure(state="disabled")

    def on_closing(self):
        if self.downloader.is_downloading:
            if messagebox.askyesno("Exit", "Download in progress. Cancel and exit?"):
                self.downloader.cancel()
                self.destroy()
        else:
            self.destroy()


# ======================== MAIN ========================
def check_ffmpeg():
    import subprocess
    try:
        subprocess.run(["ffmpeg", "-version"], capture_output=True, check=True)
        return True
    except:
        return False

if __name__ == "__main__":
    if not check_ffmpeg():
        print("WARNING: ffmpeg not found. MP3 and high-quality video may fail.")
    app = YTDLoader()
    if not check_ffmpeg():
        messagebox.showwarning("Missing ffmpeg", "ffmpeg not found.\nConversion to MP3 and video merging may not work.\nInstall ffmpeg and ensure it's in PATH.")
    app.mainloop()