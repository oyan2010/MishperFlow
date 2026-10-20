# MishperFlow - Unlimited, Private & Free Voice-to-Text Dictation 🎙️⚡

An open-source, 100% on-device alternative to paid SaaS dictation tools like WhisperFlow. **MishperFlow** provides unlimited speech-to-text with zero subscriptions, zero cloud latency, and complete privacy — your audio never leaves your machine.

---

## 🌟 Why MishperFlow?

| Feature | Paid SaaS (WhisperFlow, etc.) | **MishperFlow** (This Project) |
|---|---|---|
| **Cost** | Monthly subscription ($15 - $30/mo) | **100% Free Forever** |
| **Limits** | Capped audio hours / words | **Unlimited Dictation** |
| **Privacy** | Audio streamed to remote cloud | **100% On-Device & Private** |
| **Speed** | Dependent on internet & API queues | **Instant local GPU/CPU inference** |
| **Hotkey Workflow** | Limited window support | **Global Hotkey anywhere in OS** |

---

## ✨ Features

- **Global Push-to-Talk / Toggle Dictation**: Trigger voice dictation anywhere in Windows with a single hotkey.
- **State-of-the-art Accuracy**: Powered by `faster-whisper` (CTranslate2 implementation of OpenAI Whisper).
- **Auto-Paste to Active Window**: Transcribes your voice and instantly types or copies directly to your clipboard/active input field.
- **Modern Floating Indicator**: Minimalist tray icon and floating status indicator that stays discreetly out of your way.
- **Zero Internet Required**: Runs completely offline after local model setup.

---

## 🛠️ Installation & Setup

1. **Clone the repository**:
   ```bash
   git clone https://github.com/oyan2010/MishperFlow.git
   cd MishperFlow
   ```

2. **Set up a virtual environment (recommended)**:
   ```bash
   python -m venv venv
   # On Windows:
   venv\Scripts\activate
   ```

3. **Install dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

4. **Run the Application**:
   ```bash
   python main.py
   ```

---

## 📦 Tech Stack

- **Speech Recognition**: [faster-whisper](https://github.com/SYSTRAN/faster-whisper) (OpenAI Whisper on CTranslate2)
- **Audio Capture**: PyAudio
- **GUI & Tray**: PySide6 (Qt)
- **Global Input**: keyboard, pyperclip
- **Language**: Python 3.10+
