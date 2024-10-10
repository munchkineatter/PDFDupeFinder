import os
import hashlib
from PyQt5.QtWidgets import (QApplication, QMainWindow, QPushButton, QFileDialog, QVBoxLayout, QWidget, QProgressBar, 
                             QListWidget, QHBoxLayout, QLabel, QFrame, QScrollArea, QListWidgetItem, QMessageBox,
                             QTextEdit)
from PyQt5.QtCore import Qt, QThread, pyqtSignal
from PyQt5.QtGui import QColor, QPalette, QPixmap, QImage
import fitz  # PyMuPDF

class PDFScanner(QThread):
    progress_update = pyqtSignal(int)
    scan_complete = pyqtSignal(dict)
    error_occurred = pyqtSignal(str)

    def __init__(self, folder_path):
        super().__init__()
        self.folder_path = folder_path

    def run(self):
        try:
            pdf_files = {}
            total_files = sum([len(files) for _, _, files in os.walk(self.folder_path)])
            processed_files = 0

            for root, _, files in os.walk(self.folder_path):
                for file in files:
                    if file.lower().endswith('.pdf'):
                        file_path = os.path.join(root, file)
                        file_hash = self.calculate_hash(file_path)
                        if file_hash in pdf_files:
                            pdf_files[file_hash].append(file_path)
                        else:
                            pdf_files[file_hash] = [file_path]
                    
                    processed_files += 1
                    self.progress_update.emit(int(processed_files / total_files * 100))

            print(f"Scan complete. Found {len(pdf_files)} unique PDFs.")
            self.scan_complete.emit(pdf_files)
        except Exception as e:
            self.error_occurred.emit(str(e))

    def calculate_hash(self, file_path):
        hasher = hashlib.md5()
        with open(file_path, 'rb') as f:
            buf = f.read(65536)
            while len(buf) > 0:
                hasher.update(buf)
                buf = f.read(65536)
        return hasher.hexdigest()

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("PDF Duplicate Finder")
        self.setGeometry(100, 100, 1600, 800)
        self.setMinimumSize(1200, 600)
        self.setMaximumSize(2000, 1200)
        self.setup_ui()
        self.setup_dark_theme()
        self.pdf_groups = {}

    def setup_ui(self):
        central_widget = QWidget()
        main_layout = QHBoxLayout(central_widget)
        main_layout.setSpacing(0)
        main_layout.setContentsMargins(0, 0, 0, 0)

        # Left toolbar (fixed width)
        self.toolbar = QFrame()
        self.toolbar.setFrameShape(QFrame.StyledPanel)
        self.toolbar.setFixedWidth(150)
        toolbar_layout = QVBoxLayout(self.toolbar)
        toolbar_layout.setContentsMargins(10, 10, 10, 10)

        self.select_folder_button = QPushButton("Select Folder")
        self.select_folder_button.clicked.connect(self.select_folder)
        toolbar_layout.addWidget(self.select_folder_button)

        self.scan_button = QPushButton("Scan for Duplicates")
        self.scan_button.clicked.connect(self.start_scan)
        self.scan_button.setEnabled(False)
        toolbar_layout.addWidget(self.scan_button)

        toolbar_layout.addStretch()

        self.progress_bar = QProgressBar()
        self.progress_bar.setTextVisible(False)
        self.progress_bar.setFixedHeight(5)
        toolbar_layout.addWidget(self.progress_bar)

        # Middle section with file lists (expandable)
        self.middle_section = QWidget()
        middle_layout = QVBoxLayout(self.middle_section)

        self.original_list = QListWidget()
        self.original_list.setAlternatingRowColors(True)
        self.original_list.itemClicked.connect(self.preview_original)
        original_container = QWidget()
        original_layout = QVBoxLayout(original_container)
        original_layout.addWidget(QLabel("Original Files"))
        original_layout.addWidget(self.original_list)

        self.duplicate_list = QListWidget()
        self.duplicate_list.setAlternatingRowColors(True)
        self.duplicate_list.itemClicked.connect(self.preview_duplicate)
        duplicate_container = QWidget()
        duplicate_layout = QVBoxLayout(duplicate_container)
        duplicate_layout.addWidget(QLabel("Duplicate Files"))
        duplicate_layout.addWidget(self.duplicate_list)

        middle_layout.addWidget(original_container)
        middle_layout.addWidget(duplicate_container)

        # Right side with PDF previews and properties (fixed width)
        self.right_side_container = QWidget()
        self.right_side_container.setFixedWidth(600)
        right_side_layout = QHBoxLayout(self.right_side_container)

        # PDF previews
        preview_container = QWidget()
        preview_layout = QVBoxLayout(preview_container)

        self.original_preview = QLabel("Original PDF Preview")
        self.original_preview.setAlignment(Qt.AlignCenter)
        self.original_preview_scroll = QScrollArea()
        self.original_preview_scroll.setWidget(self.original_preview)
        self.original_preview_scroll.setWidgetResizable(True)
        self.original_preview_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.original_preview_scroll.setStyleSheet("background-color: #353535;")

        self.duplicate_preview = QLabel("Duplicate PDF Preview")
        self.duplicate_preview.setAlignment(Qt.AlignCenter)
        self.duplicate_preview_scroll = QScrollArea()
        self.duplicate_preview_scroll.setWidget(self.duplicate_preview)
        self.duplicate_preview_scroll.setWidgetResizable(True)
        self.duplicate_preview_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.duplicate_preview_scroll.setStyleSheet("background-color: #353535;")

        preview_layout.addWidget(self.original_preview_scroll)
        preview_layout.addWidget(self.duplicate_preview_scroll)

        # Properties windows
        properties_container = QWidget()
        properties_layout = QVBoxLayout(properties_container)

        self.original_properties = QTextEdit()
        self.original_properties.setReadOnly(True)
        self.original_properties.setStyleSheet("background-color: #424242; color: #E0E0E0;")
        properties_layout.addWidget(QLabel("Original PDF Properties"))
        properties_layout.addWidget(self.original_properties)

        self.duplicate_properties = QTextEdit()
        self.duplicate_properties.setReadOnly(True)
        self.duplicate_properties.setStyleSheet("background-color: #424242; color: #E0E0E0;")
        properties_layout.addWidget(QLabel("Duplicate PDF Properties"))
        properties_layout.addWidget(self.duplicate_properties)

        right_side_layout.addWidget(preview_container)
        right_side_layout.addWidget(properties_container)

        # Main layout
        main_layout.addWidget(self.toolbar)
        main_layout.addWidget(self.middle_section)
        main_layout.addWidget(self.right_side_container)

        self.setCentralWidget(central_widget)

        self.folder_path = None
        self.scanner = None

    def setup_dark_theme(self):
        dark_palette = QPalette()
        dark_palette.setColor(QPalette.Window, QColor(53, 53, 53))
        dark_palette.setColor(QPalette.WindowText, Qt.white)
        dark_palette.setColor(QPalette.Base, QColor(25, 25, 25))
        dark_palette.setColor(QPalette.AlternateBase, QColor(53, 53, 53))
        dark_palette.setColor(QPalette.ToolTipBase, Qt.white)
        dark_palette.setColor(QPalette.ToolTipText, Qt.white)
        dark_palette.setColor(QPalette.Text, Qt.white)
        dark_palette.setColor(QPalette.Button, QColor(53, 53, 53))
        dark_palette.setColor(QPalette.ButtonText, QColor(200, 200, 200))  # Lighter gray for button text
        dark_palette.setColor(QPalette.BrightText, Qt.red)
        dark_palette.setColor(QPalette.Link, QColor(42, 130, 218))
        dark_palette.setColor(QPalette.Highlight, QColor(42, 130, 218))
        dark_palette.setColor(QPalette.HighlightedText, Qt.black)
        self.setPalette(dark_palette)

        # Additional styling for buttons
        self.setStyleSheet("""
            QPushButton {
                color: #E0E0E0;
                background-color: #424242;
                border: 1px solid #555555;
                padding: 5px;
                border-radius: 3px;
            }
            QPushButton:hover {
                background-color: #4A4A4A;
            }
            QPushButton:pressed {
                background-color: #383838;
            }
            QPushButton:disabled {
                color: #888888;
                background-color: #2A2A2A;
            }
            QScrollArea, QListWidget {
                background-color: #424242;
                border: 2px solid #2A2A2A;
                border-radius: 5px;
            }
            QLabel {
                color: #E0E0E0;
                background-color: transparent;
            }
            QScrollBar:vertical {
                border: none;
                background: #424242;
                width: 10px;
                margin: 0px 0px 0px 0px;
            }
            QScrollBar::handle:vertical {
                background: #636363;
                min-height: 20px;
                border-radius: 5px;
            }
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
                height: 0px;
            }
            QScrollBar:horizontal {
                border: none;
                background: #424242;
                height: 10px;
                margin: 0px 0px 0px 0px;
            }
            QScrollBar::handle:horizontal {
                background: #636363;
                min-width: 20px;
                border-radius: 5px;
            }
            QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {
                width: 0px;
            }
        """)

        # Add styling for QProgressBar
        self.setStyleSheet(self.styleSheet() + """
            QProgressBar {
                background-color: #2A2A2A;
                border: none;
                border-radius: 2px;
            }
            QProgressBar::chunk {
                background-color: #4A4A4A;
                border-radius: 2px;
            }
        """)

        # Update the stylesheet for QListWidget to make text easier to read
        self.setStyleSheet(self.styleSheet() + """
            QListWidget {
                background-color: #2A2A2A;
                color: #E0E0E0;
                border: 2px solid #1A1A1A;
                border-radius: 5px;
            }
            QListWidget::item {
                padding: 5px;
            }
            QListWidget::item:selected {
                background-color: #4A4A4A;
            }
            QListWidget::item:alternate {
                background-color: #353535;
            }
        """)

    def select_folder(self):
        self.folder_path = QFileDialog.getExistingDirectory(self, "Select Folder")
        if self.folder_path:
            print(f"Selected folder: {self.folder_path}")
            self.scan_button.setEnabled(True)

    def start_scan(self):
        print("Starting scan...")
        self.original_list.clear()
        self.duplicate_list.clear()
        self.progress_bar.setValue(0)
        self.scanner = PDFScanner(self.folder_path)
        self.scanner.progress_update.connect(self.update_progress)
        self.scanner.scan_complete.connect(self.display_results)
        self.scanner.error_occurred.connect(self.show_error)
        self.scanner.start()

    def update_progress(self, value):
        self.progress_bar.setValue(value)

    def display_results(self, pdf_files):
        print("Displaying results...")
        self.pdf_groups.clear()
        for file_hash, file_paths in pdf_files.items():
            if len(file_paths) > 1:
                original = file_paths[0]
                duplicates = file_paths[1:]
                self.pdf_groups[original] = duplicates
                self.original_list.addItem(original)
                for path in duplicates:
                    self.duplicate_list.addItem(path)
        
        print(f"Added {self.original_list.count()} original files and {self.duplicate_list.count()} duplicates to the lists.")

    def show_error(self, error_message):
        QMessageBox.critical(self, "Error", f"An error occurred: {error_message}")

    def preview_pdf(self, file_path, preview_label, properties_widget):
        try:
            doc = fitz.open(file_path)
            page = doc.load_page(0)  # Load the first page
            
            # Get the size of the preview area
            preview_size = preview_label.parent().size()
            
            # Calculate zoom factor to fit the page within the preview area
            zoom_height = preview_size.height() / page.rect.height
            zoom_width = preview_size.width() / page.rect.width
            zoom = min(zoom_height, zoom_width) * 0.95  # Use 95% of the smaller zoom to add a small margin
            
            mat = fitz.Matrix(zoom, zoom)
            pix = page.get_pixmap(matrix=mat)
            img = QImage(pix.samples, pix.width, pix.height, pix.stride, QImage.Format_RGB888)
            pixmap = QPixmap.fromImage(img)
            
            # Set the pixmap without changing the label's size
            preview_label.setPixmap(pixmap.scaled(preview_size, Qt.KeepAspectRatio, Qt.SmoothTransformation))
            
            # Center the preview label in the scroll area
            scroll_area = preview_label.parent()
            if isinstance(scroll_area, QScrollArea):
                scroll_area.setAlignment(Qt.AlignCenter)
            
            # Update properties
            self.update_properties(file_path, doc, properties_widget)
            
            doc.close()
        except Exception as e:
            preview_label.setText(f"Error previewing PDF: {str(e)}")

    def update_properties(self, file_path, doc, properties_widget):
        properties = f"File: {os.path.basename(file_path)}\n"
        properties += f"Path: {file_path}\n"
        properties += f"Pages: {len(doc)}\n"
        properties += f"File size: {os.path.getsize(file_path) / 1024:.2f} KB\n"
        
        if doc.metadata:
            for key, value in doc.metadata.items():
                if value:
                    properties += f"{key}: {value}\n"
        
        properties_widget.setText(properties)

    def preview_original(self, item):
        file_path = item.text()
        self.preview_pdf(file_path, self.original_preview, self.original_properties)
        
        # Select corresponding duplicates
        self.duplicate_list.clearSelection()
        if file_path in self.pdf_groups:
            for i in range(self.duplicate_list.count()):
                if self.duplicate_list.item(i).text() in self.pdf_groups[file_path]:
                    self.duplicate_list.item(i).setSelected(True)
        
        # Preview the first duplicate if available
        if self.pdf_groups.get(file_path):
            self.preview_pdf(self.pdf_groups[file_path][0], self.duplicate_preview, self.duplicate_properties)

    def preview_duplicate(self, item):
        file_path = item.text()
        self.preview_pdf(file_path, self.duplicate_preview, self.duplicate_properties)
        
        # Select corresponding original
        self.original_list.clearSelection()
        for original, duplicates in self.pdf_groups.items():
            if file_path in duplicates:
                for i in range(self.original_list.count()):
                    if self.original_list.item(i).text() == original:
                        self.original_list.item(i).setSelected(True)
                        self.preview_pdf(original, self.original_preview, self.original_properties)
                        break
                break

if __name__ == "__main__":
    app = QApplication([])
    window = MainWindow()
    window.show()
    app.exec_()