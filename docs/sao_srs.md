# Software Requirements Specification (SRS) for Sao

## 1. Introduction

### 1.1 Purpose
This Software Requirements Specification (SRS) defines the functional and non-functional requirements for **Sao**, a lightweight, minimalist AI chat agent application. This document serves as the authoritative blueprint for developers, architects, and future contributors to ensure the system is built to the exact specifications defined herein. 

### 1.2 Scope
Sao is a locally-hosted desktop application designed for solo developers. It provides a bloat-free Graphical User Interface (GUI) to interact with large language models (LLMs) and execute local tools via the Model Context Protocol (MCP). The system explicitly includes multi-model hot-switching, chat and metadata persistence via SQLite, and streaming responses. 

To maintain its lightweight nature, Sao strictly excludes multi-agent orchestration, contextual memory injection across sessions, multimodal attachments (files/images), voice input/output, and cloud synchronization. It operates as a local-first interface, relying on external network access only for API calls to cloud-based LLMs.

### 1.3 Definitions and Acronyms
* **API:** Application Programming Interface.
* **gRPC:** A high-performance, open-source universal RPC framework.
* **GUI:** Graphical User Interface.
* **IPC:** Inter-Process Communication.
* **LLM:** Large Language Model (e.g., OpenAI, Anthropic, Ollama).
* **MCP:** Model Context Protocol; a standardized interface for connecting AI models to external tools and data sources.
* **LiteLLM:** A Python library that normalizes API calls to various LLM providers.
* **FlatBuffers:** An efficient cross-platform serialization library.
* **SQLite:** A C-language library that implements a small, fast, self-contained, high-reliability SQL database engine.

### 1.4 References
* IEEE Std 830-1998, IEEE Recommended Practice for Software Requirements Specifications.
* ISO/IEC 29148:2018, Systems and software engineering — Life cycle processes — Requirements engineering.
* LiteLLM Official Documentation.
* Model Context Protocol (MCP) Official Specification.

### 1.5 Document Overview
This document is organized into ten main sections. Section 2 provides a high-level overview of the product. Section 3 details the specific functional requirements. Section 4 covers non-functional characteristics like performance and security. Sections 5, 6, and 7 describe the architecture, data structures, and external interfaces. Section 8 walks through core use cases. Section 9 identifies constraints, risks, and open questions. Section 10 contains the appendix.

---

## 2. Overall Description

### 2.1 Product Perspective
Sao is a standalone desktop application. It acts as an intermediary layer between a human user and various LLM backends (both local and cloud-based). It utilizes a decoupled architecture where the UI communicates with a Python-based backend service via gRPC and FlatBuffers, ensuring high performance and UI responsiveness while the backend handles LLM routing and MCP tool execution.

### 2.2 Product Functions
The core capabilities of Sao include:
* Real-time text-based conversational interface with streaming AI responses.
* Dynamic switching of the active LLM provider during an active chat session.
* Execution of local tools and scripts exposed via connected MCP servers.
* Persistent, local logging of all conversational histories and backend metadata (e.g., model used, tools called).
* Single-session scoping guided by a single, unalterable system prompt.

### 2.3 User Classes and Characteristics
The primary user is a **Solo Developer**. This user is highly technical, prefers clean and unobtrusive interfaces, values local control over data, and requires quick access to AI assistance and local tool execution without the overhead of heavy enterprise IDEs or complex agentic platforms.

### 2.4 Operating Environment
* **Supported OS:** Windows 10/11, macOS 13+, Ubuntu/Debian-based Linux distributions.
* **Execution:** Runs natively on the host machine as a local executable/script.
* **Network:** Requires internet access for routing calls to OpenAI, Anthropic, and GitHub Copilot. Can operate fully offline if connected to a local model (e.g., Ollama) and local MCP servers.

### 2.5 Design and Implementation Constraints
* The system must be developed entirely in Python.
* The system prompt must be hardcoded; users are prevented from editing it at runtime.
* GitHub Copilot authentication must strictly utilize LiteLLM's internal handling rather than a custom OAuth implementation.
* Contextual memory must not carry over between distinct chat sessions.

### 2.6 Assumptions & Dependencies
* **Dependency:** The user has valid credentials/API keys or an active subscription for the external LLMs they intend to use.
* **Dependency:** Python 3.10 or higher is installed on the target machine (if running from source).
* **Assumption:** Local MCP servers are configured and running independently or spun up by the application environment as background processes.

---

## 3. Functional Requirements

### 3.1 Chat Interface and Processing
* **FR-001: [User] shall [input text queries into a chat interface] so that [they can communicate with the AI model].**
    * *Preconditions:* Application is running; a model is selected.
    * *Postconditions:* User query is displayed on the UI and transmitted to the backend.
    * *Edge Cases:* Empty input (ignore), excessively large text input (truncate or warn based on model token limits).
* **FR-002: [System] shall [stream text responses from the LLM back to the GUI] so that [the user experiences low latency reading].**
    * *Preconditions:* A valid request was sent to the LLM.
    * *Postconditions:* UI updates incrementally with new tokens.
    * *Edge Cases:* Network disconnection mid-stream (display partial response and connection error message).

### 3.2 LLM Hot-Switching
* **FR-003: [User] shall [select a different LLM from a persistent dropdown menu at any time] so that [the next turn of the conversation utilizes the newly selected model].**
    * *Preconditions:* Dropdown is populated with available models.
    * *Postconditions:* The backend router updates the active model parameter for the next API call.
    * *Edge Cases:* Switching to an unauthenticated model (prompt user for configuration or show authentication error upon next message).
* **FR-004: [System] shall [route GitHub Copilot requests through LiteLLM's internal Copilot handler] so that [authentication and token management are abstracted from the core application logic].**
    * *Preconditions:* User selects the GitHub Copilot model.
    * *Postconditions:* Request succeeds using LiteLLM device flow or cached token.

### 3.3 MCP Integration
* **FR-005: [System] shall [connect to configured MCP servers upon startup] so that [the active LLM can access external tools].**
    * *Preconditions:* MCP server configurations are present in a local configuration file.
    * *Postconditions:* Tool schemas are loaded and appended to LLM API requests.
* **FR-006: [System] shall [execute tool calls requested by the LLM via the MCP SDK and return the result to the LLM] so that [the LLM can complete the user's prompt using external data].**
    * *Preconditions:* The LLM returns a valid tool_call payload.
    * *Postconditions:* The tool output is appended to the message history and the LLM is queried again for a final response.
    * *Edge Cases:* Tool execution fails or times out (return error string to the LLM so it can inform the user).

### 3.4 History and Data Persistence
* **FR-007: [System] shall [save all user inputs, LLM responses, and metadata to a local SQLite database] so that [the user can review past sessions].**
    * *Preconditions:* SQLite database file is accessible and writable.
    * *Postconditions:* A new row is committed for each turn of the conversation.
    * *Edge Cases:* Database file is locked by another process (retry logic implemented).

### 3.5 System Prompt Enforcement
* **FR-008: [System] shall [prepend a static, hardcoded system prompt to the beginning of every new session context] so that [the AI behaves according to the predefined developer constraints].**
    * *Preconditions:* A new chat session is initiated.
    * *Postconditions:* The system prompt is the first hidden message in the payload sent to LiteLLM.

---

## 4. Non-Functional Requirements

### 4.1 Performance
* **NFR-001:** The GUI must remain fully responsive (no blocking/freezing) during LLM generation and tool execution.
* **NFR-002:** The serialization overhead using FlatBuffers via gRPC between the GUI and backend must not introduce a latency greater than 50ms per message chunk.

### 4.2 Security
* **NFR-003:** All API keys and authentication tokens must be stored strictly on the local file system (e.g., environment variables or encrypted local store). No data shall be transmitted to third parties except the direct LLM providers.
* **NFR-004:** MCP tool execution must be strictly scoped to the capabilities defined by the connected MCP servers; the core application will not execute arbitrary system commands outside of the MCP protocol.

### 4.3 Scalability
* **NFR-005:** The local SQLite database must be optimized to load the most recent 100 messages of a chat history in under 500ms, regardless of the total size of the database.

### 4.4 Usability
* **NFR-006:** The UI must adhere to a minimalist design paradigm. The model hot-switch dropdown must be persistently visible on the main screen without requiring navigation to a settings menu.

### 4.5 Maintainability
* **NFR-007:** The application architecture must separate GUI rendering logic from LLM/MCP orchestration logic to allow for easy swapping of UI frameworks or backend models.

### 4.6 Portability
* **NFR-008:** The codebase must execute natively on Windows, macOS, and Linux without requiring OS-specific compilation steps beyond standard Python package installations.

---

## 5. System Architecture Overview

### 5.1 Component Breakdown
1. **Frontend (GUI Client):** Built with either PyQt6 or CustomTkinter. Manages user interactions, renders chat bubbles, and handles the model selection state.
2. **IPC Layer (gRPC & FlatBuffers):** A high-speed local loopback channel. The GUI serializes requests into FlatBuffers and streams them via gRPC to the backend.
3. **Backend (AI Core):** A Python process that receives user input.
4. **LLM Router (LiteLLM):** Normalizes schemas and handles API communication to OpenAI, Anthropic, Ollama, and GitHub Copilot.
5. **Tool Orchestrator (MCP SDK):** Manages connections to independent MCP Servers, maps tool schemas to LiteLLM, and handles execution callbacks.
6. **Persistence Layer (SQLite):** A local `.sqlite3` file storing session metadata and text history.

### 5.2 Tech Stack Rationale
* **Python:** Provides the most robust ecosystem for AI tooling (LiteLLM, official MCP SDK) and desktop GUIs.
* **LiteLLM:** Eliminates the need to write custom API connectors for each model provider and handles complex auth flows like Copilot natively.
* **gRPC/FlatBuffers:** Chosen over standard REST/JSON for the MCP/Backend-to-GUI communication to provide zero-copy serialization, ensuring the UI thread is never bottlenecked by heavy token streams.
* **SQLite:** Requires zero setup for the user, operates entirely locally, and perfectly maps to the requirement of isolated session histories.

---

## 6. Data Requirements

### 6.1 Entities and Attributes
* **Session:**
    * `session_id` (UUID, Primary Key)
    * `created_at` (Timestamp)
    * `title` (String)
* **Message:**
    * `message_id` (UUID, Primary Key)
    * `session_id` (UUID, Foreign Key)
    * `role` (Enum: 'user', 'assistant', 'system', 'tool')
    * `content` (Text)
    * `timestamp` (Timestamp)
* **Metadata:**
    * `metadata_id` (UUID, Primary Key)
    * `message_id` (UUID, Foreign Key)
    * `model_used` (String, e.g., 'github_copilot', 'gpt-4o')
    * `tool_calls` (JSON string of MCP tools invoked during this turn)

### 6.2 Entity Relationships
* One `Session` contains Many `Messages` (1:N).
* One `Message` contains One `Metadata` record (1:1).

### 6.3 Retention & Privacy
All data is stored locally on the user's disk in a defined application data directory (e.g., `~/.sao/sao_history.db`). Data is retained indefinitely until the user manually deletes the database file or clears it via a UI command (if implemented). No telemetry or chat data is synced to the cloud.

---

## 7. External Interface Requirements

### 7.1 User Interfaces
* **Main Chat Window:** A scrollable pane displaying message history. User messages align right; assistant messages align left.
* **Input Area:** A multiline text box at the bottom of the window. Submits on `Enter` (or `Ctrl+Enter`).
* **Header Bar:** Contains the persistent dropdown menu for LLM hot-switching.
* **Tool Indicators:** Small visual cues (e.g., an icon or italic text) appearing in the assistant's message block indicating when an MCP tool was executed and what it was called.

### 7.2 Software Interfaces
* **LiteLLM API:** The system interacts with `litellm.completion` and `litellm.acompletion` methods, passing standardized OpenAI-format message arrays.
* **MCP Protocol:** The system acts as an MCP Host, utilizing standard JSON-RPC over `stdio` or `SSE` (as supported by the MCP Python SDK) to fetch tool lists and execute tool calls on connected MCP servers.

### 7.3 Communication Interfaces
* **Internal IPC:** The GUI and Backend communicate over `localhost` via a dedicated gRPC port (e.g., `50051`). Messages are encoded using FlatBuffers defined by a rigid `.fbs` schema file.

---

## 8. Use Cases

### UC-001: Chat with Cloud LLM (GitHub Copilot)
* **Actor:** Solo Developer
* **Precondition:** App is open. Network connection is active.
* **Main Flow:**
    1. Actor selects "GitHub Copilot" from the header dropdown.
    2. Actor types a coding question and presses send.
    3. GUI serializes the message and sends it via gRPC to the AI Core.
    4. AI Core appends the hardcoded system prompt and routes to LiteLLM.
    5. LiteLLM authenticates and streams the response.
    6. AI Core streams the FlatBuffers response back to the GUI.
    7. GUI renders the text. AI Core saves the turn to SQLite.
* **Alternate Flow (Auth Required):** If LiteLLM lacks a valid Copilot token, it triggers a device authorization flow. The backend logs the auth URL, and the GUI displays it to the user. User authenticates via browser, and the flow resumes.
* **Postcondition:** Answer is displayed; metadata logs "github_copilot" as the model used.

### UC-002: Execute MCP Tool
* **Actor:** Solo Developer / AI Assistant
* **Precondition:** An MCP server (e.g., a local file reader) is connected.
* **Main Flow:**
    1. Actor asks the AI to summarize a local project file.
    2. AI Core sends the request to the LLM along with the available MCP tool schema.
    3. LLM returns a `tool_call` request to read the file.
    4. AI Core intercepts the tool call and routes it to the correct MCP server using the MCP SDK.
    5. MCP server returns the file contents.
    6. AI Core appends the file contents to the chat context and queries the LLM again.
    7. LLM streams the final summary to the user.
* **Postcondition:** The requested file is summarized in the GUI; SQLite records the specific tool called in the metadata table.

### UC-003: Hot-switch Model Mid-Conversation
* **Actor:** Solo Developer
* **Precondition:** A chat session is currently active utilizing a local model (e.g., Ollama).
* **Main Flow:**
    1. Actor realizes the local model is struggling with a complex query.
    2. Actor clicks the persistent dropdown and selects "Anthropic Claude 3.5 Sonnet".
    3. Actor types a follow-up clarification and presses send.
    4. The GUI sends the request with the newly selected model ID attached to the FlatBuffer payload.
    5. The AI Core routes the new message (and previous session context) to Anthropic via LiteLLM.
* **Postcondition:** The conversation continues seamlessly using the new model.

---

## 9. Constraints, Risks & Open Questions

### 9.1 Technical Constraints
* **Memory Limits:** The explicit exclusion of vector databases and long-term memory means the application is constrained by the maximum context window of the selected model. Once a session exceeds this window, the backend must truncate older messages.
* **IPC Overhead:** While FlatBuffers and gRPC are highly efficient, maintaining the dual-process architecture requires careful lifecycle management to ensure background processes are terminated when the GUI is closed.

### 9.2 Risks with Mitigations
* **Risk:** Breaking changes in third-party LLM APIs.
    * *Mitigation:* Heavy reliance on LiteLLM abstracts this risk. Version pinning for LiteLLM is required to ensure stability.
* **Risk:** GUI thread freezing during long LLM responses or slow MCP tool executions.
    * *Mitigation:* All gRPC calls from the UI must be fully asynchronous. The GUI framework event loop must not block while waiting for streaming chunks.

### 9.3 Open Questions
This document recognizes the following unresolved decisions which require resolution prior to entering the implementation phase:
1. **Final GUI framework: CustomTkinter vs PyQt6.** Both are viable Python native GUI libraries. PyQt6 offers more robust threading and standard widgets, but CustomTkinter provides a faster path to a modern, minimalist dark-mode aesthetic out of the box. A spike solution is recommended to evaluate performance with async gRPC streaming.
2. **Which MCP tools/servers to bundle or recommend out of the box.** While the infrastructure supports any standard MCP server, the initial deployment configuration needs a definitive list of recommended servers (e.g., local filesystem access, git operations) to ensure immediate utility for the solo developer upon first install.

---

## 10. Appendix

### 10.1 Glossary
* **Solo Developer:** A software engineer working independently, requiring high-leverage tools without the enterprise administrative overhead.
* **Hot-Switching:** The act of changing the active computing resource (in this case, the LLM) without restarting the application or resetting the current workflow context.
* **Device Flow:** An OAuth 2.0 extension that enables devices with limited input capabilities (or terminal/CLI apps) to obtain user authorization by instructing the user to visit a URL on a secondary device/browser.

### 10.2 Revision History

| Version | Date | Author | Description |
| :--- | :--- | :--- | :--- |
| 1.0 | 2026-06-26 | Senior System Architect | Initial Draft derived from App Specifications. |