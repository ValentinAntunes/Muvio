import sys
import os
os.environ["QT_STYLE_OVERRIDE"] = "Fusion"

def resource_path(relative_path: str) -> str:
    """
    Retorna o caminho correto do recurso tanto em modo normal
    quanto empacotado com PyInstaller (usa sys._MEIPASS).
    """
    if hasattr(sys, "_MEIPASS"):
        return os.path.join(sys._MEIPASS, relative_path)
    return os.path.join(os.path.dirname(os.path.abspath(__file__)), relative_path)


from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLineEdit, QPushButton, QListWidget, QListWidgetItem, QComboBox,
    QFileDialog, QLabel, QProgressBar, QMessageBox, QGroupBox,
    QRadioButton, QSizePolicy, QFrame
)
from PyQt6.QtCore import Qt, QThread, pyqtSignal
from PyQt6.QtGui import QPixmap
from yt_dlp import YoutubeDL

class SearchThread(QThread):
    results_ready = pyqtSignal(list)
    error = pyqtSignal(str)

    def __init__(self, query: str):
        super().__init__()
        self.query = query

    def run(self):
        try:
            ydl_opts = {'quiet': True, 'extract_flat': True}
            with YoutubeDL(ydl_opts) as ydl:
                results = ydl.extract_info(f"ytsearch10:{self.query}", download=False)
                videos = results.get('entries', [])
                self.results_ready.emit(videos)
        except Exception as e:
            self.error.emit(str(e))

class DownloadThread(QThread):
    progress = pyqtSignal(float)
    finished = pyqtSignal(str)
    error = pyqtSignal(str)

    def __init__(self, url: str, output_path: str, format_type: str, quality: str):
        super().__init__()
        self.url = url
        self.output_path = output_path
        self.format_type = format_type  
        self.quality = quality          

    def progress_hook(self, d: dict):
        if d.get('status') == 'downloading':
            total = d.get('total_bytes') or d.get('total_bytes_estimate', 0)
            downloaded = d.get('downloaded_bytes', 0)
            if total > 0:
                self.progress.emit((downloaded / total) * 100)

    def run(self):
        try:
            from yt_dlp import YoutubeDL

            ffmpeg_path = resource_path("ffmpeg.exe")

            if self.format_type == 'audio':
                ydl_opts = {
                    'format': 'bestaudio[ext=m4a]/bestaudio',
                    'outtmpl': os.path.join(self.output_path, '%(title)s.%(ext)s'),
                    'progress_hooks': [self.progress_hook],
                    'ffmpeg_location': ffmpeg_path,
                    "postprocessors": [
                        {
                            "key": "FFmpegExtractAudio",
                            "preferredcodec": "m4a",
                            "preferredquality": "192",
                        }
                    ],
                }
            else:
                if self.quality == "best":
                    format_str = "bestvideo+bestaudio"
                elif self.quality == "1080p":
                    format_str = "bestvideo[height<=1080]+bestaudio"
                else: 
                    format_str = "bestvideo[height<=720]+bestaudio"

                ydl_opts = {
                    "format": format_str,
                    "outtmpl": os.path.join(self.output_path, "%(title)s.%(ext)s"),
                    "merge_output_format": "mp4",
                    "ffmpeg_location": ffmpeg_path,
                    "postprocessors": [
                        {
                            "key": "FFmpegVideoConvertor",
                            "preferedformat": "mp4",
                        },
                        {
                            "key": "FFmpegMetadata",
                        }
                    ],
                    "postprocessor_args": {
                        "ffmpeg": [
                            "-c", "copy",
                            "-c:a", "aac",
                            "-b:a", "192k",
                            "-movflags", "+faststart"
                        ]
                    },
                    "progress_hooks": [self.progress_hook],
                }

            with YoutubeDL(ydl_opts) as ydl:
                ydl.download([self.url])

            self.finished.emit("Download concluído!")

        except Exception as e:
            self.error.emit(str(e))

class YouTubeDownloader(QMainWindow):

    def __init__(self):
        super().__init__()
        self.setWindowTitle("Muvio - Download Music and Video")

        self.resize(650, 750)
        self.setMinimumSize(650, 750)

        self.output_path = os.path.expanduser("~/Downloads")
        self.selected_url = None

        self.setup_ui()

    def set_width_percent(self, widget, percent: float):
        widget.setFixedWidth(int(self.width() * percent))

    def setup_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        layout = QVBoxLayout(central)
        layout.setSpacing(15)
        layout.setContentsMargins(20, 20, 20, 20)

        logo_label = QLabel()
        logo_pixmap = QPixmap(resource_path("logo.png")).scaled(
            150, 150,
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation
        )
        logo_label.setPixmap(logo_pixmap)
        logo_label.setAlignment(Qt.AlignmentFlag.AlignCenter)

        logo_container = QHBoxLayout()
        logo_container.addStretch()
        logo_container.addWidget(logo_label)
        logo_container.addStretch()
        layout.addLayout(logo_container)

        link_group = QGroupBox("📎 Download com Link")
        link_layout = QVBoxLayout(link_group)

        self.link_input = QLineEdit()
        self.link_input.setPlaceholderText("Cole o link do YouTube aqui...")
        self.link_input.setStyleSheet(self.input_style())
        link_layout.addWidget(self.link_input)

        layout.addWidget(link_group)

        search_group = QGroupBox("🔍 Pesquisar Vídeos")
        search_layout = QVBoxLayout(search_group)

        search_row = QHBoxLayout()

        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Digite sua pesquisa...")
        self.search_input.setStyleSheet(self.input_style())
        self.search_input.returnPressed.connect(self.search_videos)

        search_row.addWidget(self.search_input)

        search_btn = QPushButton("Pesquisar")
        search_btn.setStyleSheet(self.button_style("#FF0000"))
        search_btn.clicked.connect(self.search_videos)

        search_row.addWidget(search_btn)
        search_layout.addLayout(search_row)

        layout.addWidget(search_group)

        self.overlay = QFrame(self)
        self.overlay.setFrameShape(QFrame.Shape.StyledPanel)
        self.overlay.setStyleSheet("""
            QFrame {
                background: white;
                border: 2px solid #ddd;
                border-radius: 8px;
            }
        """)
        self.overlay.hide()

        overlay_layout = QVBoxLayout(self.overlay)
        overlay_layout.setContentsMargins(5, 5, 5, 5)

        self.results_overlay = QListWidget()
        self.results_overlay.setStyleSheet("""
            QListWidget {
                background: white;
                border: none;
            }
            QListWidget::item {
                padding: 10px;
            }
            QListWidget::item:selected {
                background: #ffebee;
                color: #c00;
            }
        """)
        self.set_width_percent(self.results_overlay, 0.727)
        self.set_width_percent(self.overlay, 0.757)
        overlay_layout.addWidget(self.results_overlay)

        self.results_overlay.itemClicked.connect(self.select_video)

        self.results_list = QListWidget()
        self.results_list.setMinimumHeight(100)
        self.results_list.setSizePolicy(QSizePolicy.Policy.Expanding,
                                        QSizePolicy.Policy.Expanding)
        self.results_list.setStyleSheet("""
            QListWidget {
                border: 2px solid #ddd;
                border-radius: 8px;
                padding: 5px;
                background: #fafafa;
            }
            QListWidget::item {
                padding: 10px;
                border-bottom: 1px solid #eee;
            }
            QListWidget::item:selected {
                background: #ffebee;
                color: #c00;
            }
        """)
        layout.addWidget(self.results_list)
        self.results_list.itemClicked.connect(self.select_video)

        options_group = QGroupBox("⚙️ Opções de Download")
        options_layout = QVBoxLayout(options_group)

        type_layout = QHBoxLayout()
        type_layout.addWidget(QLabel("Tipo:"))
        self.audio_radio = QRadioButton("🎵 Áudio (M4A)")
        self.video_radio = QRadioButton("🎬 Vídeo (MP4)")
        self.video_radio.setChecked(True)
        self.audio_radio.toggled.connect(self.toggle_quality)

        type_layout.addWidget(self.audio_radio)
        type_layout.addWidget(self.video_radio)
        type_layout.addStretch()
        options_layout.addLayout(type_layout)

        quality_layout = QHBoxLayout()
        quality_layout.addWidget(QLabel("Qualidade:"))
        self.quality_combo = QComboBox()
        self.quality_combo.addItems(["Melhor Qualidade", "1080p", "720p"])
        self.quality_combo.setStyleSheet("""
            QComboBox {
                padding: 2px;
                width: 110px;
                border: 2px solid #ddd;
                border-radius: 6px;
                background: white;
            }
        """)
        quality_layout.addWidget(self.quality_combo)
        quality_layout.addStretch()
        options_layout.addLayout(quality_layout)

        folder_layout = QHBoxLayout()
        folder_layout.addWidget(QLabel("Destino:"))

        self.folder_label = QLabel(self.output_path)
        self.folder_label.setStyleSheet("color: #666; font-size: 12px;")
        folder_layout.addWidget(self.folder_label, 1)

        folder_btn = QPushButton("📁 Escolher")
        folder_btn.setStyleSheet(
            self.button_style("#666") +
            "QPushButton { padding: 3px 10px; }"
        )
        folder_btn.clicked.connect(self.choose_folder)
        folder_layout.addWidget(folder_btn)

        options_layout.addLayout(folder_layout)

        layout.addWidget(options_group)

        self.progress_bar = QProgressBar()
        self.progress_bar.setStyleSheet("""
            QProgressBar {
                border: 2px solid #ddd;
                border-radius: 8px;
                text-align: center;
                height: 25px;
            }
            QProgressBar::chunk {
                background: qlineargradient(
                    x1:0, y1:0, x2:1, y2:0,
                    stop:0 #FF0000, stop:1 #FF6B6B
                );
                border-radius: 6px;
            }
        """)
        layout.addWidget(self.progress_bar)

        download_btn = QPushButton("⬇ Download")
        download_btn.setStyleSheet(self.button_style("#FF0000", large=True))
        download_btn.clicked.connect(self.start_download)
        layout.addWidget(download_btn)

        self.status_label = QLabel("Pronto para baixar!")
        self.status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.status_label.setStyleSheet("color: #666; font-size: 12px;")
        layout.addWidget(self.status_label)

    def input_style(self) -> str:
        return """
            QLineEdit {
                padding: 10px;
                border: 2px solid #ddd;
                border-radius: 8px;
                font-size: 14px;
                background: white;
            }
            QLineEdit:focus {
                border-color: #FF0000;
            }
        """

    def button_style(self, color: str, large: bool = False) -> str:
        padding = "12px 24px" if large else "6px 12px"
        size = "16px" if large else "13px"
        return f"""
            QPushButton {{
                background: {color};
                color: white;
                border: none;
                border-radius: 8px;
                padding: {padding};
                font-size: {size};
                font-weight: bold;
            }}
            QPushButton:hover {{
                background: #cc0000;
            }}
            QPushButton:pressed {{
                background: #990000;
            }}
        """

    def toggle_quality(self):
        self.quality_combo.setEnabled(not self.audio_radio.isChecked())

    def search_videos(self):
        query = self.search_input.text().strip()
        if not query:
            return

        self.status_label.setText("Pesquisando...")
        self.results_overlay.clear()
        self.results_list.clear()

        input_pos = self.search_input.mapToGlobal(self.search_input.rect().bottomLeft())
        parent_pos = self.mapFromGlobal(input_pos)

        self.overlay.setGeometry(
            parent_pos.x(),
            parent_pos.y(),
            self.search_input.width() + 60,
            300
        )

        self.overlay.raise_()
        self.overlay.show()

        self.search_thread = SearchThread(query)
        self.search_thread.results_ready.connect(self.show_results)
        self.search_thread.error.connect(self.show_error)
        self.search_thread.start()

    def show_results(self, videos):
        self.results_overlay.clear()
        self.results_list.clear()

        for video in videos:
            if not video:
                continue

            title = video.get('title', 'Sem título')
            url = video.get('url', '')

            item_overlay = QListWidgetItem(f"🎬 {title}")
            item_overlay.setData(Qt.ItemDataRole.UserRole, url)
            self.results_overlay.addItem(item_overlay)

            item_fixed = QListWidgetItem(f"🎬 {title}")
            item_fixed.setData(Qt.ItemDataRole.UserRole, url)
            self.results_list.addItem(item_fixed)

        self.status_label.setText(f"{len(videos)} resultados encontrados")

    def select_video(self, item: QListWidgetItem):
        self.overlay.hide()
        self.selected_url = item.data(Qt.ItemDataRole.UserRole)
        self.status_label.setText(f"Selecionado: {item.text()[:50]}...")

    def mousePressEvent(self, event):
        if self.overlay.isVisible():
            if not self.overlay.geometry().contains(event.pos()):
                self.overlay.hide()
        super().mousePressEvent(event)

    def choose_folder(self):
        folder = QFileDialog.getExistingDirectory(self, "Escolher Pasta")
        if folder:
            self.output_path = folder
            self.folder_label.setText(folder)

    def start_download(self):
        url = self.link_input.text().strip() or self.selected_url
        if not url:
            QMessageBox.warning(self, "Aviso", "Cole um link ou selecione um vídeo!")
            return

        format_type = 'audio' if self.audio_radio.isChecked() else 'video'
        quality_map = {"Melhor Qualidade": "best", "1080p": "1080p", "720p": "720p"}
        quality = quality_map[self.quality_combo.currentText()]

        self.progress_bar.setValue(0)
        self.status_label.setText("Baixando...")

        self.download_thread = DownloadThread(url, self.output_path, format_type, quality)
        self.download_thread.progress.connect(
            lambda p: self.progress_bar.setValue(int(p))
        )
        self.download_thread.finished.connect(self.download_complete)
        self.download_thread.error.connect(self.show_error)
        self.download_thread.start()

    def download_complete(self, msg: str):
        self.progress_bar.setValue(100)
        self.status_label.setText(msg)
        QMessageBox.information(self, "Sucesso", msg)

    def show_error(self, error: str):
        self.status_label.setText("Erro!")
        QMessageBox.critical(self, "Erro", error)

if __name__ == "__main__":
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    window = YouTubeDownloader()
    window.show()
    sys.exit(app.exec())
