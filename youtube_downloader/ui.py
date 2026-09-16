from __future__ import annotations

from pathlib import Path
from typing import Any

from PySide6.QtCore import QThread, Qt
from PySide6.QtGui import QCloseEvent
from PySide6.QtWidgets import (
    QApplication,
    QButtonGroup,
    QComboBox,
    QFileDialog,
    QFormLayout,
    QFrame,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QRadioButton,
    QSpinBox,
    QTableWidget,
    QTableWidgetItem,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from .models import DownloadRequest, PlaylistInfo
from .selection import build_range, normalize_custom_selection
from .workers import AnalyzerWorker, DownloadWorker


APP_STYLE = """
QMainWindow, QWidget { background: #111318; color: #f3f4f6; }
QFrame#card, QGroupBox {
    background: #181b22;
    border: 1px solid #2a2e38;
    border-radius: 10px;
}
QGroupBox { margin-top: 12px; padding: 14px 12px 12px 12px; font-weight: 600; }
QGroupBox::title { subcontrol-origin: margin; left: 12px; padding: 0 4px; }
QLineEdit, QComboBox, QSpinBox, QTextEdit, QTableWidget {
    background: #101217;
    border: 1px solid #343944;
    border-radius: 7px;
    padding: 7px;
    selection-background-color: #ff334f;
}
QLineEdit:focus, QComboBox:focus, QSpinBox:focus { border: 1px solid #ff4962; }
QPushButton {
    background: #2b303b;
    border: 1px solid #3b414e;
    border-radius: 7px;
    padding: 8px 13px;
    font-weight: 600;
}
QPushButton:hover { background: #353b48; }
QPushButton:disabled { color: #777d89; background: #242832; }
QPushButton#primary { background: #e6213b; border-color: #ff435a; color: white; }
QPushButton#primary:hover { background: #f12b45; }
QProgressBar {
    border: 1px solid #343944;
    border-radius: 7px;
    background: #101217;
    text-align: center;
    min-height: 18px;
}
QProgressBar::chunk { background: #e6213b; border-radius: 6px; }
QHeaderView::section { background: #20242c; border: 0; padding: 7px; font-weight: 600; }
"""


def _format_duration(seconds: int | None) -> str:
    if seconds is None:
        return "—"
    hours, rem = divmod(seconds, 3600)
    minutes, secs = divmod(rem, 60)
    if hours:
        return f"{hours:d}:{minutes:02d}:{secs:02d}"
    return f"{minutes:d}:{secs:02d}"


def _format_bytes_per_second(value: Any) -> str:
    try:
        speed = float(value)
    except (TypeError, ValueError):
        return "—"
    units = ["o/s", "Ko/s", "Mo/s", "Go/s"]
    unit = 0
    while speed >= 1024 and unit < len(units) - 1:
        speed /= 1024
        unit += 1
    return f"{speed:.1f} {units[unit]}"


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("Playlist Downloader")
        self.resize(980, 780)
        self.setMinimumSize(800, 650)
        self.setStyleSheet(APP_STYLE)

        self.playlist_info: PlaylistInfo | None = None
        self.analyzer_thread: QThread | None = None
        self.analyzer_worker: AnalyzerWorker | None = None
        self.download_thread: QThread | None = None
        self.download_worker: DownloadWorker | None = None

        self._build_ui()
        self._connect_signals()
        self._sync_selection_controls()
        self._sync_format_controls()

    def _build_ui(self) -> None:
        root = QWidget()
        root_layout = QVBoxLayout(root)
        root_layout.setContentsMargins(18, 18, 18, 18)
        root_layout.setSpacing(12)
        self.setCentralWidget(root)

        title = QLabel("Playlist Downloader")
        title.setStyleSheet("font-size: 24px; font-weight: 700;")
        subtitle = QLabel("Télécharge une playlist entière, une plage ou des vidéos précises.")
        subtitle.setStyleSheet("color: #a7acb8;")
        root_layout.addWidget(title)
        root_layout.addWidget(subtitle)

        url_card = QFrame()
        url_card.setObjectName("card")
        url_layout = QHBoxLayout(url_card)
        self.url_input = QLineEdit()
        self.url_input.setPlaceholderText("https://www.youtube.com/playlist?list=...")
        self.analyze_button = QPushButton("Analyser")
        self.analyze_button.setObjectName("primary")
        url_layout.addWidget(self.url_input, 1)
        url_layout.addWidget(self.analyze_button)
        root_layout.addWidget(url_card)

        self.playlist_summary = QLabel("Colle une URL de playlist puis clique sur Analyser.")
        self.playlist_summary.setStyleSheet("color: #a7acb8;")
        root_layout.addWidget(self.playlist_summary)

        self.table = QTableWidget(0, 3)
        self.table.setHorizontalHeaderLabels(["#", "Titre", "Durée"])
        self.table.horizontalHeader().setStretchLastSection(False)
        self.table.horizontalHeader().setSectionResizeMode(0, self.table.horizontalHeader().ResizeMode.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(1, self.table.horizontalHeader().ResizeMode.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(2, self.table.horizontalHeader().ResizeMode.ResizeToContents)
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.setMaximumHeight(235)
        root_layout.addWidget(self.table)

        controls = QHBoxLayout()
        controls.setSpacing(12)
        root_layout.addLayout(controls)

        selection_group = QGroupBox("Sélection")
        selection_layout = QGridLayout(selection_group)
        self.all_radio = QRadioButton("Toute la playlist")
        self.range_radio = QRadioButton("Plage")
        self.custom_radio = QRadioButton("Personnalisée")
        self.all_radio.setChecked(True)
        self.selection_group = QButtonGroup(self)
        for button in (self.all_radio, self.range_radio, self.custom_radio):
            self.selection_group.addButton(button)

        self.range_start = QSpinBox()
        self.range_start.setRange(1, 99999)
        self.range_end = QSpinBox()
        self.range_end.setRange(1, 99999)
        self.range_end.setValue(10)
        self.custom_items = QLineEdit()
        self.custom_items.setPlaceholderText("Ex. 1,3,7,10-15")

        range_row = QHBoxLayout()
        range_row.addWidget(QLabel("De"))
        range_row.addWidget(self.range_start)
        range_row.addWidget(QLabel("à"))
        range_row.addWidget(self.range_end)

        selection_layout.addWidget(self.all_radio, 0, 0, 1, 2)
        selection_layout.addWidget(self.range_radio, 1, 0)
        selection_layout.addLayout(range_row, 1, 1)
        selection_layout.addWidget(self.custom_radio, 2, 0)
        selection_layout.addWidget(self.custom_items, 2, 1)
        controls.addWidget(selection_group, 1)

        settings_group = QGroupBox("Téléchargement")
        settings_layout = QFormLayout(settings_group)
        self.format_combo = QComboBox()
        self.format_combo.addItem("MP4 — compatible QuickTime (H.264 + AAC)", "mp4")
        self.format_combo.addItem("WebM — vidéo", "webm")
        self.format_combo.addItem("MP3 — audio", "mp3")
        self.format_combo.addItem("M4A — audio", "m4a")

        self.quality_combo = QComboBox()
        self.quality_combo.addItem("Meilleure disponible", None)
        for height in (1080, 720, 480, 360):
            self.quality_combo.addItem(f"{height}p max", height)

        output_row = QWidget()
        output_layout = QHBoxLayout(output_row)
        output_layout.setContentsMargins(0, 0, 0, 0)
        self.output_input = QLineEdit(str(Path.home() / "Downloads"))
        self.browse_button = QPushButton("…")
        self.browse_button.setFixedWidth(42)
        output_layout.addWidget(self.output_input, 1)
        output_layout.addWidget(self.browse_button)

        settings_layout.addRow("Format", self.format_combo)
        settings_layout.addRow("Qualité", self.quality_combo)
        settings_layout.addRow("Dossier", output_row)
        controls.addWidget(settings_group, 1)

        action_row = QHBoxLayout()
        self.download_button = QPushButton("Télécharger")
        self.download_button.setObjectName("primary")
        self.download_button.setEnabled(False)
        self.cancel_button = QPushButton("Annuler")
        self.cancel_button.setEnabled(False)
        action_row.addWidget(self.download_button)
        action_row.addWidget(self.cancel_button)
        action_row.addStretch(1)
        root_layout.addLayout(action_row)

        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        self.progress_label = QLabel("Prêt")
        self.progress_label.setStyleSheet("color: #a7acb8;")
        root_layout.addWidget(self.progress_bar)
        root_layout.addWidget(self.progress_label)

        self.log_view = QTextEdit()
        self.log_view.setReadOnly(True)
        self.log_view.setMaximumHeight(150)
        self.log_view.setPlaceholderText("Les détails du téléchargement apparaîtront ici.")
        root_layout.addWidget(self.log_view)

    def _connect_signals(self) -> None:
        self.analyze_button.clicked.connect(self.start_analysis)
        self.download_button.clicked.connect(self.start_download)
        self.cancel_button.clicked.connect(self.cancel_download)
        self.browse_button.clicked.connect(self.choose_output_dir)
        self.format_combo.currentIndexChanged.connect(self._sync_format_controls)
        for button in (self.all_radio, self.range_radio, self.custom_radio):
            button.toggled.connect(self._sync_selection_controls)

    def _sync_selection_controls(self) -> None:
        range_enabled = self.range_radio.isChecked()
        self.range_start.setEnabled(range_enabled)
        self.range_end.setEnabled(range_enabled)
        self.custom_items.setEnabled(self.custom_radio.isChecked())

    def _sync_format_controls(self) -> None:
        output_format = self.format_combo.currentData()
        self.quality_combo.setEnabled(output_format in {"mp4", "webm"})

    def choose_output_dir(self) -> None:
        folder = QFileDialog.getExistingDirectory(self, "Choisir le dossier de destination")
        if folder:
            self.output_input.setText(folder)

    def start_analysis(self) -> None:
        url = self.url_input.text().strip()
        if not url:
            QMessageBox.warning(self, "URL manquante", "Ajoute l'URL d'une playlist YouTube.")
            return
        if self.analyzer_thread and self.analyzer_thread.isRunning():
            return

        self.playlist_info = None
        self.download_button.setEnabled(False)
        self.analyze_button.setEnabled(False)
        self.table.setRowCount(0)
        self.playlist_summary.setText("Analyse de la playlist…")

        thread = QThread(self)
        worker = AnalyzerWorker(url)
        worker.moveToThread(thread)
        thread.started.connect(worker.run)
        worker.finished.connect(self._analysis_finished)
        worker.error.connect(self._analysis_failed)
        worker.finished.connect(thread.quit)
        worker.error.connect(thread.quit)
        thread.finished.connect(worker.deleteLater)
        thread.finished.connect(thread.deleteLater)
        thread.finished.connect(self._analysis_thread_done)
        self.analyzer_thread = thread
        self.analyzer_worker = worker
        thread.start()

    def _analysis_finished(self, info: PlaylistInfo) -> None:
        self.playlist_info = info
        self.playlist_summary.setText(
            f"{info.title} — {len(info.entries)} vidéo(s)"
            + (f" — {info.uploader}" if info.uploader else "")
        )
        self.table.setRowCount(len(info.entries))
        for row, entry in enumerate(info.entries):
            index_item = QTableWidgetItem(str(entry.index))
            index_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self.table.setItem(row, 0, index_item)
            self.table.setItem(row, 1, QTableWidgetItem(entry.title))
            duration_item = QTableWidgetItem(_format_duration(entry.duration))
            duration_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self.table.setItem(row, 2, duration_item)

        last_index = max(entry.index for entry in info.entries)
        self.range_start.setMaximum(last_index)
        self.range_end.setMaximum(last_index)
        self.range_end.setValue(last_index)
        self.download_button.setEnabled(True)

    def _analysis_failed(self, message: str) -> None:
        self.playlist_summary.setText("Analyse impossible.")
        QMessageBox.critical(self, "Erreur d'analyse", message)

    def _analysis_thread_done(self) -> None:
        self.analyze_button.setEnabled(True)
        self.analyzer_thread = None
        self.analyzer_worker = None

    def _playlist_items(self) -> str | None:
        if self.all_radio.isChecked():
            return None
        if self.range_radio.isChecked():
            return build_range(self.range_start.value(), self.range_end.value())
        return normalize_custom_selection(self.custom_items.text())

    def start_download(self) -> None:
        if not self.playlist_info:
            QMessageBox.warning(self, "Playlist non analysée", "Analyse d'abord la playlist.")
            return
        if self.download_thread and self.download_thread.isRunning():
            return

        try:
            playlist_items = self._playlist_items()
        except ValueError as exc:
            QMessageBox.warning(self, "Sélection invalide", str(exc))
            return

        output_dir_text = self.output_input.text().strip()
        if not output_dir_text:
            QMessageBox.warning(self, "Dossier manquant", "Choisis un dossier de destination.")
            return

        request = DownloadRequest(
            url=self.url_input.text().strip(),
            output_dir=Path(output_dir_text),
            playlist_items=playlist_items,
            output_format=self.format_combo.currentData(),
            quality=self.quality_combo.currentData(),
        )

        self.progress_bar.setValue(0)
        self.progress_label.setText("Préparation du téléchargement…")
        self.log_view.clear()
        self.download_button.setEnabled(False)
        self.analyze_button.setEnabled(False)
        self.cancel_button.setEnabled(True)

        thread = QThread(self)
        worker = DownloadWorker(request)
        worker.moveToThread(thread)
        thread.started.connect(worker.run)
        worker.progress.connect(self._download_progress)
        worker.log.connect(self._append_log)
        worker.finished.connect(self._download_finished)
        worker.cancelled.connect(self._download_cancelled)
        worker.error.connect(self._download_failed)
        worker.finished.connect(thread.quit)
        worker.cancelled.connect(thread.quit)
        worker.error.connect(thread.quit)
        thread.finished.connect(worker.deleteLater)
        thread.finished.connect(thread.deleteLater)
        thread.finished.connect(self._download_thread_done)
        self.download_thread = thread
        self.download_worker = worker
        thread.start()

    def cancel_download(self) -> None:
        if self.download_worker:
            self.cancel_button.setEnabled(False)
            self.progress_label.setText("Annulation en cours…")
            self.download_worker.cancel()

    def _download_progress(self, data: dict[str, Any]) -> None:
        status = data.get("status")
        filename = Path(data.get("filename") or "").name
        if status == "downloading":
            downloaded = data.get("downloaded_bytes") or 0
            total = data.get("total_bytes") or data.get("total_bytes_estimate") or 0
            percent = int(downloaded * 100 / total) if total else 0
            self.progress_bar.setValue(max(0, min(100, percent)))
            speed = _format_bytes_per_second(data.get("speed"))
            eta = data.get("eta")
            eta_text = f"{int(eta)} s" if isinstance(eta, (int, float)) else "—"
            self.progress_label.setText(f"{filename} — {percent}% — {speed} — ETA {eta_text}")
        elif status == "finished":
            self.progress_bar.setValue(100)
            self.progress_label.setText(f"Traitement : {filename}")

    def _append_log(self, message: str) -> None:
        if message.strip():
            self.log_view.append(message.strip())

    def _download_finished(self) -> None:
        self.progress_bar.setValue(100)
        self.progress_label.setText("Téléchargement terminé.")
        QMessageBox.information(self, "Terminé", "Le téléchargement est terminé.")

    def _download_cancelled(self) -> None:
        self.progress_label.setText("Téléchargement annulé.")
        self._append_log("Téléchargement annulé par l'utilisateur.")

    def _download_failed(self, message: str) -> None:
        self.progress_label.setText("Le téléchargement a échoué.")
        QMessageBox.critical(self, "Erreur de téléchargement", message)

    def _download_thread_done(self) -> None:
        self.download_button.setEnabled(self.playlist_info is not None)
        self.analyze_button.setEnabled(True)
        self.cancel_button.setEnabled(False)
        self.download_thread = None
        self.download_worker = None

    def closeEvent(self, event: QCloseEvent) -> None:
        if self.download_thread and self.download_thread.isRunning():
            answer = QMessageBox.question(
                self,
                "Téléchargement en cours",
                "Un téléchargement est en cours. L'annuler et fermer l'application ?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No,
            )
            if answer != QMessageBox.StandardButton.Yes:
                event.ignore()
                return
            if self.download_worker:
                self.download_worker.cancel()
            self.download_thread.quit()
            self.download_thread.wait(1500)
        event.accept()
