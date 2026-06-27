import sys
import uuid
import threading
import json
import time
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QVBoxLayout, QWidget, 
    QTextEdit, QLineEdit, QPushButton, QComboBox, QHBoxLayout,
    QDialog, QFormLayout, QDialogButtonBox, QLabel, QMessageBox
)
from PyQt6.QtCore import pyqtSignal, QObject, pyqtSlot, QSettings, QThread
from .client import SaoClient

PROVIDERS = ["OpenAI", "Anthropic", "GitHub", "Google"]

class WorkerSignals(QObject):
    chunk_received = pyqtSignal(str)
    finished = pyqtSignal()

class ModelFetcherThread(QThread):
    models_fetched = pyqtSignal(list)
    error = pyqtSignal(str)

    def __init__(self, provider):
        super().__init__()
        self.provider = provider

    def run(self):
        try:
            models = SaoClient().list_models(self.provider)
            self.models_fetched.emit(models)
        except Exception as e:
            self.error.emit(f"Error: {str(e)}")


class SettingsDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Settings")
        self.resize(350, 250)
        
        self.settings = QSettings("Sao", "SaoApp")
        
        layout = QVBoxLayout(self)
        form_layout = QFormLayout()
        
        self.provider_combo = QComboBox()
        self.provider_combo.addItems(PROVIDERS)
        
        current_provider = self.settings.value("provider", "OpenAI")
        if current_provider in PROVIDERS:
            self.provider_combo.setCurrentText(current_provider)
            
        form_layout.addRow(QLabel("Provider:"), self.provider_combo)
        
        # API Keys
        self.key_inputs = {}
        for prov in PROVIDERS:
            inp = QLineEdit()
            inp.setEchoMode(QLineEdit.EchoMode.Password)
            inp.setText(self.settings.value(f"{prov}_api_key", ""))
            self.key_inputs[prov] = inp
            form_layout.addRow(QLabel(f"{prov} API Key:"), inp)
            
        layout.addLayout(form_layout)
        
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)
        
    def accept(self):
        self.settings.setValue("provider", self.provider_combo.currentText())
        for prov, inp in self.key_inputs.items():
            self.settings.setValue(f"{prov}_api_key", inp.text().strip())
        super().accept()

class SaoApp(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Sao - Minimalist AI")
        self.resize(800, 600)
        
        self.client = SaoClient()
        self.session_id = str(uuid.uuid4())
        self.messages_history = []
        self.settings = QSettings("Sao", "SaoApp")
        
        self.signals = WorkerSignals()
        self.signals.chunk_received.connect(self.append_chunk)
        self.signals.finished.connect(self.on_generation_finished)
        
        self.fetcher_thread = None
        
        self.init_ui()
        if self.model_selector.count() == 0:
            self.refresh_models()
        
    def init_ui(self):
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        layout = QVBoxLayout(central_widget)
        
        # Header layout
        header_layout = QHBoxLayout()
        self.model_selector = QComboBox()
        
        self.refresh_btn = QPushButton("Refresh Models")
        self.refresh_btn.clicked.connect(self.refresh_models)
        
        self.settings_btn = QPushButton("Settings")
        self.settings_btn.clicked.connect(self.open_settings)
        
        header_layout.addWidget(self.model_selector)
        header_layout.addWidget(self.refresh_btn)
        header_layout.addStretch()
        header_layout.addWidget(self.settings_btn)
        
        # Chat display
        self.chat_display = QTextEdit()
        self.chat_display.setReadOnly(True)
        
        # Input area
        input_layout = QHBoxLayout()
        self.input_field = QLineEdit()
        self.input_field.returnPressed.connect(self.send_message)
        self.send_button = QPushButton("Send")
        self.send_button.clicked.connect(self.send_message)
        input_layout.addWidget(self.input_field)
        input_layout.addWidget(self.send_button)
        
        layout.addLayout(header_layout)
        layout.addWidget(self.chat_display)
        layout.addLayout(input_layout)
        
        self.update_model_list()
        
    def refresh_models(self):
        provider = self.settings.value("provider", "OpenAI")

        self.refresh_btn.setEnabled(False)
        self.refresh_btn.setText("Fetching...")
        
        self.fetcher_thread = ModelFetcherThread(provider)
        self.fetcher_thread.models_fetched.connect(self.on_models_fetched)
        self.fetcher_thread.error.connect(self.on_fetch_error)
        self.fetcher_thread.finished.connect(self.on_fetch_finished)
        self.fetcher_thread.start()

    @pyqtSlot(list)
    def on_models_fetched(self, models):
        provider = self.settings.value("provider", "OpenAI")
        if models:
            self.settings.setValue(f"{provider}_dynamic_models", json.dumps(models))
            self.update_model_list()
            QMessageBox.information(self, "Success", f"Fetched {len(models)} models for {provider}.")
            
    @pyqtSlot(str)
    def on_fetch_error(self, err):
        QMessageBox.warning(self, "Fetch Error", f"Failed to fetch models: {err}")
        
    @pyqtSlot()
    def on_fetch_finished(self):
        self.refresh_btn.setEnabled(True)
        self.refresh_btn.setText("Refresh Models")
        
    def update_model_list(self):
        provider = self.settings.value("provider", "OpenAI")
        
        # Check dynamic models first
        dynamic_json = self.settings.value(f"{provider}_dynamic_models", "")
        try:
            models = json.loads(dynamic_json) if dynamic_json else []
        except:
            models = []
            
        usage_json = self.settings.value("model_usage", "{}")
        try:
            usage = json.loads(usage_json)
        except:
            usage = {}
            
        models_sorted = sorted(models, key=lambda m: usage.get(m, 0), reverse=True)
        
        current_model = self.model_selector.currentText()
        self.model_selector.clear()
        self.model_selector.addItems(models_sorted)
        
        # Restore previously selected model if it's still in the list
        if current_model in models_sorted:
            self.model_selector.setCurrentText(current_model)
            
    def open_settings(self):
        dialog = SettingsDialog(self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            self.update_model_list()
            if self.model_selector.count() == 0:
                self.refresh_models()

    def send_message(self):
        text = self.input_field.text().strip()
        if not text:
            return
            
        self.input_field.clear()
        self.input_field.setEnabled(False)
        self.send_button.setEnabled(False)
        
        self.chat_display.append(f"<b>You:</b> {text}<br>")
        self.chat_display.append("<b>Sao:</b> ")
        
        self.messages_history.append({"role": "user", "content": text})
        model_id = self.model_selector.currentText()
        provider = self.settings.value("provider", "OpenAI")
        
        # Track usage recency
        usage_json = self.settings.value("model_usage", "{}")
        try:
            usage = json.loads(usage_json)
        except:
            usage = {}
        usage[model_id] = time.time()
        self.settings.setValue("model_usage", json.dumps(usage))
        
        # Format model for backend
        if "/" in model_id:
            backend_model = model_id
        elif provider == "GitHub":
            backend_model = f"github_copilot/{model_id}"
        elif provider == "Anthropic":
            backend_model = f"anthropic/{model_id}"
        elif provider == "Google":
            backend_model = f"gemini/{model_id}"
        else:
            backend_model = model_id
        
        # Start background thread for gRPC streaming
        threading.Thread(target=self.stream_response, args=(backend_model,), daemon=True).start()
        
    def stream_response(self, model_id):
        full_response = ""
        try:
            for chunk, is_final in self.client.send_chat_stream(self.session_id, model_id, self.messages_history):
                if chunk:
                    full_response += chunk
                    self.signals.chunk_received.emit(chunk)
                if is_final:
                    break
            self.messages_history.append({"role": "assistant", "content": full_response})
        except Exception as e:
            self.signals.chunk_received.emit(f"<br><i>Error: {str(e)}</i>")
        finally:
            self.signals.finished.emit()
            
    @pyqtSlot(str)
    def append_chunk(self, chunk):
        # Insert plain text chunk without breaking html
        cursor = self.chat_display.textCursor()
        cursor.movePosition(cursor.MoveOperation.End)
        self.chat_display.setTextCursor(cursor)
        self.chat_display.insertPlainText(chunk)
        
    @pyqtSlot()
    def on_generation_finished(self):
        self.chat_display.append("<br>")
        self.input_field.setEnabled(True)
        self.send_button.setEnabled(True)
        self.input_field.setFocus()
        self.update_model_list() # Re-sort models after message finishes if usage changed

def main():
    app = QApplication(sys.argv)
    window = SaoApp()
    window.show()
    sys.exit(app.exec())

if __name__ == "__main__":
    main()
