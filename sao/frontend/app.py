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
from sao.config import load_last_state, save_last_state, get_env_credentials, set_env_credentials, DEFAULT_BASES

PROVIDERS = ["OpenAI", "Anthropic", "GitHub", "Google"]

class WorkerSignals(QObject):
    chunk_received = pyqtSignal(str)
    finished = pyqtSignal()

class ModelFetcherThread(QThread):
    models_fetched = pyqtSignal(str, list, int)
    error = pyqtSignal(str, str, bool, int)

    def __init__(self, provider, request_id, is_startup=False, api_base="", api_key=""):
        super().__init__()
        self.provider = provider
        self.request_id = request_id
        self.is_startup = is_startup
        self.api_base = api_base
        self.api_key = api_key

    def run(self):
        try:
            models = SaoClient().list_models(self.provider, self.api_base, self.api_key)
            self.models_fetched.emit(self.provider, models, self.request_id)
        except Exception as e:
            self.error.emit(self.provider, f"Error: {str(e)}", self.is_startup, self.request_id)


class SettingsDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Settings")
        self.resize(360, 140)
        
        self.settings = QSettings("Sao", "SaoApp")
        
        layout = QVBoxLayout(self)
        form_layout = QFormLayout()
        
        self.provider_combo = QComboBox()
        self.provider_combo.addItems(PROVIDERS)
        
        state = load_last_state()
        current_provider = self.settings.value("provider", state.get("active_provider", "OpenAI"))
        if current_provider in PROVIDERS:
            self.provider_combo.setCurrentText(current_provider)
            
        self.form_layout.addRow(QLabel("Provider:"), self.provider_combo)
        
        provider_state = state.get("providers", {}).get(current_provider, {})
        self.config_mode_combo = QComboBox()
        self.config_mode_combo.addItems(["Default", "Custom"])
        self.config_mode_combo.setCurrentText(provider_state.get("config_mode", "Default"))
        self.form_layout.addRow(QLabel("Configuration Mode:"), self.config_mode_combo)
            
        self.api_base_label = QLabel(f"{current_provider} API Base:")
        self.api_base_input = QLineEdit()
        self.api_base_input.setPlaceholderText("https://... (Optional)")
        
        self.api_key_label = QLabel(f"{current_provider} API Key:")
        self.api_key_input = QLineEdit()
        self.api_key_input.setPlaceholderText("sk-... (Optional)")
        self.api_key_input.setEchoMode(QLineEdit.EchoMode.Password)
        
        form_layout.addRow(self.api_base_label, self.api_base_input)
        form_layout.addRow(self.api_key_label, self.api_key_input)
            
        layout.addLayout(form_layout)
        layout.addWidget(QLabel("Other credentials are managed by your backend environment."))
        
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)
        
        self.provider_combo.currentTextChanged.connect(self.on_provider_changed)
        self.config_mode_combo.currentTextChanged.connect(self.on_config_mode_changed)
        self.on_provider_changed(current_provider)

    def on_provider_changed(self, text):
        state = load_last_state()
        provider_state = state.get("providers", {}).get(text, {})
        self.config_mode_combo.setCurrentText(provider_state.get("config_mode", "Default"))
        
        if text == "GitHub":
            self.config_mode_combo.hide()
            self.form_layout.labelForField(self.config_mode_combo).hide()
            self.api_base_label.hide()
            self.api_base_input.hide()
            self.api_key_label.hide()
            self.api_key_input.hide()
        else:
            self.config_mode_combo.show()
            self.form_layout.labelForField(self.config_mode_combo).show()
            self.api_base_label.show()
            self.api_base_input.show()
            self.api_key_label.show()
            self.api_key_input.show()
            self.on_config_mode_changed(self.config_mode_combo.currentText())
            
    def on_config_mode_changed(self, text):
        provider = self.provider_combo.currentText()
        if provider == "GitHub":
            return
            
        base, key = get_env_credentials(provider)
        
        if text == "Default":
            self.api_base_label.setText(f"{provider} API Base:")
            self.api_base_input.setText(DEFAULT_BASES.get(provider, ""))
            self.api_base_input.setDisabled(True)
            self.api_key_label.setText(f"{provider} API Key (Mandatory):")
        else:
            self.api_base_label.setText(f"{provider} API Base (Mandatory):")
            self.api_base_input.setText(base)
            self.api_base_input.setDisabled(False)
            self.api_key_label.setText(f"{provider} API Key (Optional):")
            
        self.api_key_input.setText(key)
        
    def accept(self):
        provider = self.provider_combo.currentText()
        config_mode = self.config_mode_combo.currentText()
        
        if provider != "GitHub":
            api_base = self.api_base_input.text().strip()
            api_key = self.api_key_input.text().strip()
            
            if config_mode == "Default" and not api_key:
                QMessageBox.warning(self, "Validation Error", "API Key is mandatory for Default configuration.")
                return
            if config_mode == "Custom" and not api_base:
                QMessageBox.warning(self, "Validation Error", "API Base is mandatory for Custom configuration.")
                return
                
            set_env_credentials(provider, api_base, api_key)
            
        self.settings.setValue("provider", provider)
        save_last_state(provider, config_mode=config_mode)
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
        
        state = load_last_state()
        active_provider = state.get("active_provider")
        if active_provider:
            self.settings.setValue("provider", active_provider)
            
        provider_state = state.get("providers", {}).get(self.settings.value("provider", "OpenAI"), {})
        self._last_model = provider_state.get("model", "")
        
        self.signals = WorkerSignals()
        self.signals.chunk_received.connect(self.append_chunk)
        self.signals.finished.connect(self.on_generation_finished)
        self.is_generating = False
        
        self.fetcher_threads = set()
        self.model_fetch_request_id = 0
        
        self.init_ui()
        self.refresh_models(is_startup=True)
        
    def init_ui(self):
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        layout = QVBoxLayout(central_widget)
        
        # Header layout
        header_layout = QHBoxLayout()
        self.model_selector = QComboBox()
        
        self.settings_btn = QPushButton("Settings")
        self.settings_btn.clicked.connect(self.open_settings)
        
        header_layout.addWidget(self.model_selector)
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
        
    def refresh_models(self, is_startup=False):
        provider = self.settings.value("provider", "OpenAI")
        state = load_last_state()
        provider_state = state.get("providers", {}).get(provider, {})
        config_mode = provider_state.get("config_mode", "Default")
        
        env_api_base, env_api_key = get_env_credentials(provider)
        api_base = DEFAULT_BASES.get(provider, "") if config_mode == "Default" else env_api_base
        api_key = env_api_key
        
        self.model_fetch_request_id += 1

        fetcher_thread = ModelFetcherThread(
            provider,
            self.model_fetch_request_id,
            is_startup=is_startup,
            api_base=api_base,
            api_key=api_key
        )
        self.fetcher_threads.add(fetcher_thread)
        fetcher_thread.models_fetched.connect(self.on_models_fetched)
        fetcher_thread.error.connect(self.on_fetch_error)
        fetcher_thread.finished.connect(self.on_fetcher_finished)
        fetcher_thread.start()

    @pyqtSlot()
    def on_fetcher_finished(self):
        fetcher_thread = self.sender()
        if fetcher_thread in self.fetcher_threads:
            self.fetcher_threads.remove(fetcher_thread)
            fetcher_thread.deleteLater()

    @pyqtSlot(str, list, int)
    def on_models_fetched(self, provider, models, request_id):
        if (
            request_id != self.model_fetch_request_id
            or provider != self.settings.value("provider", "OpenAI")
        ):
            return

        self.settings.setValue(f"{provider}_dynamic_models", json.dumps(models))
        self.update_model_list()
        if not models:
            QMessageBox.warning(self, "No Models", f"No models are currently available for {provider}.")
            
    @pyqtSlot(str, str, bool, int)
    def on_fetch_error(self, provider, err, is_startup, request_id):
        if (
            request_id != self.model_fetch_request_id
            or provider != self.settings.value("provider", "OpenAI")
        ):
            return

        if is_startup:
            msg = QMessageBox(self)
            msg.setIcon(QMessageBox.Icon.Critical)
            msg.setWindowTitle("Startup Error")
            msg.setText(f"Could not load models: {err}\n\nCheck your API key and network connection.")
            open_settings_btn = msg.addButton("Open Settings", QMessageBox.ButtonRole.ActionRole)
            msg.addButton("Quit", QMessageBox.ButtonRole.RejectRole)
            msg.exec()
            if msg.clickedButton() == open_settings_btn:
                self.open_settings()
            else:
                QApplication.instance().quit()
        else:
            QMessageBox.warning(self, "Fetch Error", f"Failed to fetch models: {err}")
        
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
        if self._last_model in models_sorted:
            self.model_selector.setCurrentText(self._last_model)
        elif current_model in models_sorted:
            self.model_selector.setCurrentText(current_model)
        
        try:
            self.model_selector.currentTextChanged.disconnect(self.on_model_changed)
        except TypeError:
            pass
        self.model_selector.currentTextChanged.connect(self.on_model_changed)
        
        self.update_interaction_state()

    @pyqtSlot(str)
    def on_model_changed(self, text):
        if text:
            self._last_model = text
            provider = self.settings.value("provider", "OpenAI")
            state = load_last_state()
            provider_state = state.get("providers", {}).get(provider, {})
            config_mode = provider_state.get("config_mode", "Default")
            save_last_state(provider, model=text, config_mode=config_mode)

    def update_interaction_state(self):
        has_model = self.model_selector.count() > 0 and bool(self.model_selector.currentText())
        can_send = has_model and not self.is_generating

        self.input_field.setEnabled(can_send)
        self.send_button.setEnabled(can_send)

        if has_model:
            self.input_field.setPlaceholderText("")
        else:
            self.input_field.setPlaceholderText("No model available. Refresh models or change provider in Settings.")
            
    def open_settings(self):
        dialog = SettingsDialog(self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            self.update_model_list()
            self.refresh_models()

    def send_message(self):
        model_id = self.model_selector.currentText().strip()
        if not model_id:
            QMessageBox.warning(self, "No Model Selected", "Load models before sending a message.")
            return

        text = self.input_field.text().strip()
        if not text:
            return
            
        self.input_field.clear()
        self.is_generating = True
        self.update_interaction_state()
        
        self.chat_display.append(f"<b>You:</b> {text}<br>")
        self.chat_display.append("<b>Sao:</b> ")
        
        self.messages_history.append({"role": "user", "content": text})
        provider = self.settings.value("provider", "OpenAI")
        
        # Track usage recency
        usage_json = self.settings.value("model_usage", "{}")
        try:
            usage = json.loads(usage_json)
        except:
            usage = {}
        usage[model_id] = time.time()
        self.settings.setValue("model_usage", json.dumps(usage))
        
        # Start background thread for gRPC streaming
        state = load_last_state()
        provider_state = state.get("providers", {}).get(provider, {})
        config_mode = provider_state.get("config_mode", "Default")
        
        env_api_base, env_api_key = get_env_credentials(provider)
        api_base = DEFAULT_BASES.get(provider, "") if config_mode == "Default" else env_api_base
        api_key = env_api_key
        
        threading.Thread(target=self.stream_response, args=(model_id, provider, api_base, api_key), daemon=True).start()
        
    def stream_response(self, model_id, provider, api_base, api_key):
        full_response = ""
        try:
            for chunk, is_final in self.client.send_chat_stream(self.session_id, model_id, self.messages_history, provider=provider, api_base=api_base, api_key=api_key):
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
        self.is_generating = False
        self.chat_display.append("<br>")
        self.update_interaction_state()
        self.input_field.setFocus()
        self.update_model_list() # Re-sort models after message finishes if usage changed

def main():
    app = QApplication(sys.argv)
    window = SaoApp()
    window.show()
    sys.exit(app.exec())

if __name__ == "__main__":
    main()
