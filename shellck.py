#!/usr/bin/env python
# -*- coding: utf-8 -*-
# Colorful SEO & Shell Checker with GUI by ROot-society
__author__ = 'Root-hec'
__version__ = '0.9.2'

import sys
import os
import asyncio
import aiohttp
import logging
from urllib.parse import urlparse
from typing import List, Set
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QLineEdit, QLabel, QTextEdit, QFileDialog, QProgressBar, QRadioButton
)
from PyQt6.QtCore import Qt, QThread, pyqtSignal


Shell_title = "Your Shell Title" #shell title here

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

class ShellCheckWorker(QThread):
    progress = pyqtSignal(str, str)  
    progress_value = pyqtSignal(int)  
    finished = pyqtSignal()

    def __init__(self, checker, sites, shell_title):
        super().__init__()
        self.checker = checker
        self.sites = sites
        self.checker.shell_title = shell_title
        self.total_sites = len(sites)

    def run(self):
        """Run the shell checking"""
        try:
            # Run async check_shells 
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            loop.run_until_complete(self.checker.check_shells(self.sites, self.emit_progress))
            loop.close()
        except Exception as e:
            self.progress.emit(f"Error: {str(e)}", "red")
        finally:
            self.progress_value.emit(100)
            self.finished.emit()

    def emit_progress(self, msg, color):
        self.progress.emit(msg, color)
        if self.total_sites > 0:
            checked = len(self.checker._alive_urls) + len(self.checker._dead_urls)
            percentage = int((checked / self.total_sites) * 100)
            self.progress_value.emit(percentage)

class ShellChecker:
    """Core logic for extracting SEO sites and checking shells."""
    
    def __init__(self, shell_title: str = Shell_title, max_concurrent: int = 50):# concurrent async requests
        self.shell_title = shell_title
        self.max_concurrent = max_concurrent  
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 '
                          '(KHTML, like Gecko) Chrome/91.0.4472.114 Safari/537.36'
        }
        self._alive_urls = []  
        self._dead_urls = []  

    def read_file(self, file_path: str) -> Set[str]:
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                return set(line.strip() for line in f if line.strip())
        except UnicodeDecodeError as e:
            logging.error(f"Failed to decode {file_path}: {e}")
            raise ValueError(f"Cannot decode file {file_path}. Ensure it is UTF-8 encoded.")
        except FileNotFoundError:
            logging.error(f"File not found: {file_path}")
            raise FileNotFoundError(f"File not found: {file_path}")

    def append_to_file(self, file_path: str, data: str, progress_callback):
        """Append a single URL to a file with immediate flush."""
        try:
            with open(file_path, 'a', encoding='utf-8') as f:
                f.write(data + '\n')
                f.flush()  
            progress_callback(f"Saved to {os.path.basename(file_path)}: {data}", "blue")
        except Exception as e:
            logging.error(f"Failed to append to {file_path}: {e}")
            raise IOError(f"Failed to append to {file_path}: {e}")

    def write_file(self, file_path: str, data: List[str], progress_callback):
        try:
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write('\n'.join(data) + '\n')
                f.flush()  # Ensure immediate write to disk
            progress_callback(f"Saved {len(data)} URLs to {os.path.basename(file_path)}", "green")
        except Exception as e:
            logging.error(f"Failed to write to {file_path}: {e}")
            raise IOError(f"Failed to write to {file_path}: {e}")

    def extract_seo_sites(self, shell_list_file: str, seo_list_file: str, progress_callback) -> List[str]:
        progress_callback("Extracting SEO sites from shells...", "blue")
        shell_list = self.read_file(shell_list_file)
        seo_list = self.read_file(seo_list_file)
        
        if not shell_list or not seo_list:
            progress_callback("One or both input files are empty or invalid.", "red")
            return []
        
        filtered_sites = [site for site in shell_list if any(keyword in site for keyword in seo_list)]
        
        if filtered_sites:
            self.write_file("temp.txt", filtered_sites, progress_callback)
            for site in filtered_sites:
                progress_callback(site, "yellow")
        else:
            progress_callback("No matching sites found.", "yellow")
        
        return filtered_sites

    async def check_shell(self, url: str, session: aiohttp.ClientSession) -> tuple:
        """Check if a shell is alive"""
        try:
            async with session.get(url, timeout=10, ssl=False) as response:
                text = await response.text()
                is_alive = self.shell_title in text
                return url, is_alive
        except (aiohttp.ClientError, asyncio.TimeoutError):
            return url, False

    async def check_shells(self, sites: List[str], progress_callback):
        """Check all shells concurrently with real-time updates and saving."""
        if not sites:
            progress_callback("No sites to check.", "yellow")
            return
        
        progress_callback("Checking shells...", "blue")
        self._alive_urls = []
        self._dead_urls = []
        
        # Clear output files at start
        for file in ['Alivexhell.txt', 'deadxhell.txt', 'seo.txt']:
            if os.path.exists(file):
                os.remove(file)
        
        async with aiohttp.ClientSession(headers=self.headers) as session:
            tasks = [self.check_shell(url, session) for url in sites]
            for future in asyncio.as_completed(tasks):
                url, is_alive = await future
                if is_alive:
                    progress_callback(f"[XxX] {url} => Shell Alive!", "green")
                    self._alive_urls.append(url)
                    self.append_to_file('Alivexhell.txt', url, progress_callback)
                    # Update seo.txt with unique hosts
                    unique_alive_urls = self.remove_duplicate_hosts(self._alive_urls)
                    if unique_alive_urls:
                        self.write_file('seo.txt', unique_alive_urls, progress_callback)
                else:
                    progress_callback(f"Shell Dead or Down: {url}", "red")
                    self._dead_urls.append(url)
                    self.append_to_file('deadxhell.txt', url, progress_callback)
                # Yield control to update GUI
                await asyncio.sleep(0)
        
        if not self._alive_urls:
            progress_callback("No unique alive shells found.", "yellow")
        else:
            progress_callback("[XxX] Duplicate hosts removed, final save to seo.txt", "green")

    def remove_duplicate_hosts(self, urls: List[str]) -> List[str]:
        seen_hosts = set()
        unique_urls = []
        
        for url in urls:
            host = urlparse(url).netloc
            if host and host not in seen_hosts:
                seen_hosts.add(host)
                unique_urls.append(url)
                
        return unique_urls

class ShellCheckerGUI(QMainWindow):
    """Colorful GUI for the Shell Checker and SEO"""
    
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Shell Checker by Root-hex")
        self.setGeometry(100, 100, 800, 600)
        self.checker = ShellChecker()
        self.init_ui()
        
    def init_ui(self):
        # Main widget and layout
        main_widget = QWidget()
        self.setCentralWidget(main_widget)
        layout = QVBoxLayout()
        main_widget.setLayout(layout)
        
        # Apply dark theme
        main_widget.setStyleSheet("""
            QWidget {
                background-color: #2E2E2E;
                color: #FFFFFF;
                font-family: Arial;
            }
            QLabel {
                color: #00BFFF;
                font-size: 14px;
            }
            QLineEdit {
                background-color: #3C3C3C;
                color: #FFFFFF;
                border: 1px solid #555555;
                padding: 5px;
                font-size: 12px;
            }
            QPushButton {
                background-color: #4CAF50;
                color: white;
                border: none;
                padding: 8px;
                font-size: 12px;
            }
            QPushButton:hover {
                background-color: #45a049;
            }
            QTextEdit {
                background-color: #1E1E1E;
                color: #FFFFFF;
                border: 1px solid #555555;
                font-size: 12px;
            }
            QProgressBar {
                background-color: #3C3C3C;
                color: #FFFFFF;
                border: 1px solid #555555;
                text-align: center;
            }
            QProgressBar::chunk {
                background-color: #4CAF50;
            }
            QRadioButton {
                color: #FFFFFF;
                font-size: 12px;
            }
        """)
        
        # Mode selection
        mode_layout = QHBoxLayout()
        self.seo_mode_radio = QRadioButton("SEO Mode")
        self.seo_mode_radio.setChecked(True)
        self.shell_mode_radio = QRadioButton("Shell Check Mode")
        mode_layout.addWidget(QLabel("Mode:"))
        mode_layout.addWidget(self.seo_mode_radio)
        mode_layout.addWidget(self.shell_mode_radio)
        layout.addLayout(mode_layout)
        
        # Shell list file selection
        shell_layout = QHBoxLayout()
        self.shell_list_input = QLineEdit()
        self.shell_list_input.setPlaceholderText("Select shell list file...")
        shell_browse_btn = QPushButton("Browse")
        shell_browse_btn.clicked.connect(self.browse_shell_list)
        shell_browse_btn.setStyleSheet("background-color: #2196F3;")  
        shell_layout.addWidget(QLabel("Shell List:"))
        shell_layout.addWidget(self.shell_list_input)
        shell_layout.addWidget(shell_browse_btn)
        layout.addLayout(shell_layout)
        
        # SEO list file selection (wrapped in a QWidget)
        self.seo_widget = QWidget()
        seo_layout = QHBoxLayout()
        self.seo_list_label = QLabel("SEO List:")
        self.seo_list_input = QLineEdit()
        self.seo_list_input.setPlaceholderText("Select SEO list file...")
        seo_browse_btn = QPushButton("Browse")
        seo_browse_btn.clicked.connect(self.browse_seo_list)
        seo_browse_btn.setStyleSheet("background-color: #2196F3;")   
        seo_layout.addWidget(self.seo_list_label)
        seo_layout.addWidget(self.seo_list_input)
        seo_layout.addWidget(seo_browse_btn)
        self.seo_widget.setLayout(seo_layout)
        layout.addWidget(self.seo_widget)
        
        
        self.seo_mode_radio.toggled.connect(self.toggle_seo_input)
        self.toggle_seo_input()  # Initial state
        
    
        title_layout = QHBoxLayout()
        self.shell_title_input = QLineEdit(Shell_title)
        title_layout.addWidget(QLabel("Shell Title:"))
        title_layout.addWidget(self.shell_title_input)
        layout.addLayout(title_layout)
        
        # Output text area
        self.output_text = QTextEdit()
        self.output_text.setReadOnly(True)
        
        # Button layout for Start and Clear
        button_layout = QHBoxLayout()
        self.start_btn = QPushButton("Start Checking")
        self.start_btn.clicked.connect(self.start_checking)
        self.start_btn.setStyleSheet("""
            background-color: #4CAF50;
            padding: 10px;
            font-size: 14px;
        """)
        self.clear_btn = QPushButton("Clear Output")
        self.clear_btn.clicked.connect(self.output_text.clear)
        self.clear_btn.setStyleSheet("""
            background-color: #FF4444;
            padding: 10px;
            font-size: 14px;
        """)
        button_layout.addWidget(self.start_btn)
        button_layout.addWidget(self.clear_btn)
        layout.addLayout(button_layout)
        
        # Progress bar
        self.progress_bar = QProgressBar()
        self.progress_bar.setValue(0)
        layout.addWidget(self.progress_bar)
        
        # Add output text area to layout
        layout.addWidget(QLabel("Output:"))
        layout.addWidget(self.output_text)
        
    def toggle_seo_input(self):
        is_seo_mode = self.seo_mode_radio.isChecked()
        self.seo_widget.setVisible(is_seo_mode)

    def browse_shell_list(self):
        file_path, _ = QFileDialog.getOpenFileName(self, "Select Shell List File", "", "Text Files (*.txt);;All Files (*)")
        if file_path:
            self.shell_list_input.setText(file_path)
            
    def browse_seo_list(self):
        file_path, _ = QFileDialog.getOpenFileName(self, "Select SEO List File", "", "Text Files (*.txt);;All Files (*)")
        if file_path:
            self.seo_list_input.setText(file_path)
            
    def log_message(self, message: str, color: str):
        """output text area."""
        color_map = {
            "green": "#00FF00",
            "red": "#FF0000",
            "yellow": "#FFFF00",
            "blue": "#00BFFF",
            "white": "#FFFFFF"
        }
        color_hex = color_map.get(color, "#FFFFFF")  # Default to white
        html_message = f'<span style="color:{color_hex}">{message}</span>'
        self.output_text.append(html_message)
        self.output_text.ensureCursorVisible()
        
    def start_checking(self):
        """Start the shell checking"""
        shell_list_file = self.shell_list_input.text().strip()
        seo_list_file = self.seo_list_input.text().strip()
        shell_title = self.shell_title_input.text().strip()
        is_seo_mode = self.seo_mode_radio.isChecked()
        
        if not shell_list_file:
            self.log_message("Error: Please select a shell list file.", "red")
            return
        
        if is_seo_mode and not seo_list_file:
            self.log_message("Error: Please select an SEO list file for SEO Mode.", "red")
            return
        
        if not shell_title:
            self.log_message("Error: Shell title cannot be empty.", "red")
            return
        
        self.start_btn.setEnabled(False)
        self.clear_btn.setEnabled(False)
        self.progress_bar.setValue(0)
        self.output_text.clear()
        
        try:
            if is_seo_mode:
                # SEO Mode: Extract sites first
                sites = self.checker.extract_seo_sites(shell_list_file, seo_list_file, self.log_message)
            else:
                # Shell Check Mode: Read shell list directly
                self.log_message("Reading shell list...", "blue")
                sites = list(self.checker.read_file(shell_list_file))
                if sites:
                    self.log_message(f"Found {len(sites)} shells to check.", "green")
                else:
                    self.log_message("Shell list is empty or invalid.", "red")
                    self.start_btn.setEnabled(True)
                    self.clear_btn.setEnabled(True)
                    return
            
            if not sites:
                self.start_btn.setEnabled(True)
                self.clear_btn.setEnabled(True)
                return
            
            # Start worker thread
            self.worker = ShellCheckWorker(self.checker, sites, shell_title)
            self.worker.progress.connect(self.log_message)
            self.worker.progress_value.connect(self.progress_bar.setValue)
            self.worker.finished.connect(lambda: self.start_btn.setEnabled(True))
            self.worker.finished.connect(lambda: self.clear_btn.setEnabled(True))
            self.worker.start()
            
        except Exception as e:
            self.log_message(f"Error: {str(e)}", "red")
            self.start_btn.setEnabled(True)
            self.clear_btn.setEnabled(True)

if __name__ == '__main__':
    app = QApplication(sys.argv)
    window = ShellCheckerGUI()
    window.show()
    sys.exit(app.exec())
