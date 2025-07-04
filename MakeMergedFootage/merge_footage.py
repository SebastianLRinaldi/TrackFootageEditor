import sys
import subprocess
import os
from pathlib import Path
from PyQt6.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QLabel, QListWidgetItem,
    QPushButton, QFileDialog, QMessageBox, QListWidget, QListView,
    QInputDialog, QProgressBar
)
from PyQt6.QtGui import QPixmap, QIcon, QDrag
from PyQt6.QtCore import Qt, QThread, pyqtSignal


class DraggableListWidget(QListWidget):
    def __init__(self):
        super().__init__()
        self.setViewMode(QListWidget.ViewMode.ListMode)
        self.setIconSize(QPixmap(128, 128).size())
        self.setSpacing(5)
        self.setMovement(QListView.Movement.Snap)
        self.setDragDropMode(QListWidget.DragDropMode.InternalMove)
        self.setSelectionMode(QListWidget.SelectionMode.SingleSelection)
        self.setDragEnabled(True)
        self.setAcceptDrops(True)
        self.setDropIndicatorShown(True)
        self.drag_start_pos = None

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.drag_start_pos = event.position().toPoint()
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if self.drag_start_pos is None:
            return
        if (event.position().toPoint() - self.drag_start_pos).manhattanLength() >= QApplication.startDragDistance():
            drag_item = self.currentItem()
            if drag_item:
                drag = QDrag(self)
                mime_data = self.model().mimeData(self.selectedIndexes())
                drag.setMimeData(mime_data)
                drag.exec(Qt.DropAction.MoveAction)
        super().mouseMoveEvent(event)


class MergeThread(QThread):
    finished = pyqtSignal(str)
    error = pyqtSignal(str)

    def __init__(self, files, output_file):
        super().__init__()
        self.files = files
        self.output_file = output_file

    def run(self):
        try:
            with open("files.txt", "w") as f:
                for path in self.files:
                    f.write(f"file '{path}'\n")
        except Exception as e:
            self.error.emit(f"Failed to write files.txt: {e}")
            return

        cmd = ["ffmpeg", "-f", "concat", "-safe", "0", "-i", "files.txt", "-c", "copy", self.output_file]

        try:
            process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
            _, stderr = process.communicate()

            if process.returncode != 0:
                self.error.emit(f"ffmpeg error (code {process.returncode}):\n{stderr}")
                return

            self.finished.emit(self.output_file)
        except Exception as e:
            self.error.emit(str(e))

from PyQt6.QtWidgets import QHBoxLayout

class VideoMerger(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Drag-and-Drop MP4 Merger")
        self.resize(700, 450)

        layout = QVBoxLayout()

        self.order_label = QLabel("Drag MP4 files here in the order to merge")
        layout.addWidget(self.order_label)

        self.list_widget = DraggableListWidget()
        self.list_widget.setMaximumHeight(180)
        layout.addWidget(self.list_widget)

        file_btn = QPushButton("Pick Files")
        file_btn.clicked.connect(self.pick_files)
        layout.addWidget(file_btn)

        # Horizontal layout for output file controls
        out_layout = QHBoxLayout()
        self.output_label = QLabel("Output file: (none)")
        out_layout.addWidget(self.output_label)

        self.change_output_btn = QPushButton("Change Output Location")
        self.change_output_btn.clicked.connect(self.change_output_location)
        out_layout.addWidget(self.change_output_btn)

        layout.addLayout(out_layout)

        self.merge_btn = QPushButton("Merge")
        self.merge_btn.clicked.connect(self.merge_files)
        layout.addWidget(self.merge_btn)

        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 0)  # Indeterminate
        self.progress_bar.setVisible(False)
        layout.addWidget(self.progress_bar)

        self.setLayout(layout)
        self.setAcceptDrops(True)
        self.merge_thread = None

        self.output_file_path = None  # Store output path here

    def dragEnterEvent(self, event):
        if event.mimeData().hasUrls():
            event.acceptProposedAction()

    def dropEvent(self, event):
        paths = [u.toLocalFile() for u in event.mimeData().urls()]
        mp4s = [p for p in paths if p.lower().endswith(".mp4")]
        for path in mp4s:
            self.add_video_item(path)
        self.update_default_output_path()

    def pick_files(self):
        files, _ = QFileDialog.getOpenFileNames(self, "Select MP4 Files", "", "Video Files (*.mp4)")
        for path in files:
            self.add_video_item(path)
        self.update_default_output_path()

    def add_video_item(self, file_path):
        existing_paths = [self.list_widget.item(i).data(Qt.ItemDataRole.UserRole) for i in range(self.list_widget.count())]
        if file_path in existing_paths:
            return  # skip duplicates

        thumb_path = self.create_thumbnail(file_path)
        item = QListWidgetItem(QIcon(thumb_path), os.path.basename(file_path))
        item.setData(Qt.ItemDataRole.UserRole, file_path)
        self.list_widget.addItem(item)

    def create_thumbnail(self, file_path):
        thumb = file_path + "_thumb.png"
        if not os.path.exists(thumb):
            subprocess.run([
                "ffmpeg", "-y", "-i", file_path, "-vf", "thumbnail,scale=128:72", "-frames:v", "1", thumb
            ], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        return thumb

    def update_default_output_path(self):
        count = self.list_widget.count()
        if count == 0:
            self.output_file_path = None
            self.output_label.setText("Output file: (none)")
            return

        file_paths = [
            self.list_widget.item(i).data(Qt.ItemDataRole.UserRole)
            for i in range(count)
        ]

        first_path = Path(file_paths[0])
        default_name = first_path.stem + "(MM-DD-YY)-R#.mp4"
        default_path = first_path.with_name(default_name)

        # Only update if user hasn't set a custom output path
        if self.output_file_path is None or not self.output_file_path.exists():
            self.output_file_path = default_path
            self.output_label.setText(f"Output file: {self.output_file_path}")

    def change_output_location(self):
        base_path = Path("F:\\_Small\\344 School Python\\TrackFootageEditor\\RaceStorage")  # ← your preferred default folder

        if not base_path.exists():
            base_path = Path.home()  # fallback

        default_name = self.output_file_path.name if self.output_file_path else "merged(MM-DD-YY)-R#.mp4"
        file_dialog = QFileDialog(self, "Select Output File")
        file_dialog.setAcceptMode(QFileDialog.AcceptMode.AcceptSave)
        file_dialog.setNameFilter("MP4 Video (*.mp4)")
        file_dialog.setDirectory(str(base_path))
        file_dialog.selectFile(default_name)

        if file_dialog.exec():
            selected_files = file_dialog.selectedFiles()
            if selected_files:
                selected = Path(selected_files[0])
                if selected.suffix.lower() != ".mp4":
                    selected = selected.with_suffix(".mp4")
                self.output_file_path = selected
                self.output_label.setText(f"Output file: {self.output_file_path}")

    def merge_files(self):
        count = self.list_widget.count()
        if count < 2:
            QMessageBox.warning(self, "Error", "Add at least 2 videos to merge.")
            return

        if not self.output_file_path:
            QMessageBox.warning(self, "Error", "Set output file location before merging.")
            return

        file_paths = [
            self.list_widget.item(i).data(Qt.ItemDataRole.UserRole)
            for i in range(count)
        ]

        self.merge_btn.setEnabled(False)
        self.progress_bar.setVisible(True)

        self.merge_thread = MergeThread(file_paths, str(self.output_file_path))
        self.merge_thread.finished.connect(self.merge_done)
        self.merge_thread.error.connect(self.merge_error)
        self.merge_thread.start()

    def merge_done(self, output_file):
        self.progress_bar.setVisible(False)
        self.merge_btn.setEnabled(True)
        QMessageBox.information(self, "Done", f"Merged video saved as:\n{output_file}")

    def merge_error(self, error_msg):
        self.progress_bar.setVisible(False)
        self.merge_btn.setEnabled(True)
        QMessageBox.critical(self, "Merge Error", error_msg)



if __name__ == "__main__":
    app = QApplication(sys.argv)
    win = VideoMerger()
    win.show()
    sys.exit(app.exec())
