# Real-Time E-Commerce Voicebot ("Aria") using LiveKit & Groq

[![LiveKit](https://img.shields.io/badge/LiveKit-WebRTC-blue)](https://livekit.io)
[![Groq](https://img.shields.io/badge/Groq-Llama_3.3_70B-orange)](https://groq.com)
[![Python](https://img.shields.io/badge/Python-3.13-green)](https://python.org)
[![React](https://img.shields.io/badge/React-19.0-61dafb)](https://react.dev)

A real-time, low-latency AI customer support voicebot built for e-commerce using **LiveKit WebRTC**, **Groq LLM (Llama 3.3 70B)**, **local Whisper STT**, **local Piper/PyTTSx3 TTS**, **Silero VAD**, and **Python**.

---

## 🚀 System Architecture

```
Mic (Browser) <--- WebRTC ---> LiveKit Cloud Room <--- WebRTC ---> Python Agent Worker
                                                                          |
                                                      +-------------------+-------------------+
                                                      | Voice Pipeline (VAD->STT->LLM->TTS)   |
                                                      |  - VAD: Silero VAD                    |
                                                      |  - STT: Local Whisper (faster-whisper)|
                                                      |  - LLM: Groq Llama 3.3 70B            |
                                                      |  - TTS: Local Piper / PyTTSx3         |
                                                      +---------------------------------------+
                                                                          |
                                                      +-------------------+-------------------+
                                                      | Tool Calling & Knowledge Base         |
                                                      |  - get_order_status (orders.json)     |
                                                      |  - get_product_info (products.json)   |
                                                      |  - search_faq (local RAG policy docs) |
                                                      +---------------------------------------+
```

---

## 📋 Prerequisites

1. **Python 3.10+** (Tested on Python 3.13)
2. **Node.js 18+ & npm** (Tested on Node v24.18.0)
3. **LiveKit Cloud Account** (Free tier at [cloud.livekit.io](https://cloud.livekit.io))
4. **Groq API Key** (Free tier at [console.groq.com/keys](https://console.groq.com/keys))

---

## 🔑 Credential Setup

1. Copy `backend/.env.example` to `backend/.env`:
   ```bash
   cp backend/.env.example backend/.env
   ```
2. Open `backend/.env` and insert your credentials:
   ```env
   LIVEKIT_URL=wss://<your-project>.livekit.cloud
   LIVEKIT_API_KEY=<your_livekit_api_key>
   LIVEKIT_API_SECRET=<your_livekit_api_secret>
   GROQ_API_KEY=gsk_<your_groq_api_key>
   ```

---

## 📦 Installation & Setup

### 1. Backend Setup
```bash
cd backend
python -m pip install -r requirements.txt
```

### 2. Frontend Setup
```bash
cd frontend
npm install
```

---

## 🏃 Running the Voicebot

You need **3 processes** running concurrently:

### Terminal 1: Token & API Server (FastAPI)
```bash
cd backend
python server.py
# Server will start on http://localhost:8000
```

### Terminal 2: LiveKit Agent Worker
```bash
cd backend
python agent.py dev
# Agent will connect to your LiveKit Cloud project and wait for room connections
```

### Terminal 3: Frontend Dev Server (React + Vite)
```bash
cd frontend
npm run dev
# Frontend will be accessible at http://localhost:5173
```

---

## 🎙️ Demo Test Scenarios

Open your browser to `http://localhost:5173`, click **"Start Voice Conversation"**, allow microphone permissions, and test the following four scenarios:

### Scenario 1: Backend Action (Order Tracking)
- **User speaks:** *"Hi Aria, can you check the status of my order ORD-1001?"*
- **Expected Response:** *"Order ORD-1001 for Wireless Headphones is out for delivery via FedEx, estimated to arrive today."*

### Scenario 2: Product Catalog Lookup
- **User speaks:** *"Are the wireless headphones in stock and how much do they cost?"*
- **Expected Response:** *"The Wireless Noise-Canceling Headphones cost $149.99 and we currently have 42 units in stock."*

### Scenario 3: Informational Policy Query (Local RAG)
- **User speaks:** *"What is your return policy?"*
- **Expected Response:** *"You can return items within 30 days of delivery in their original condition for a full refund or store exchange."*

### Scenario 4: Graceful Fallback (Unsupported / Ambiguous Request)
- **User speaks:** *"Can you change my shipping address to 123 Main Street?"*
- **Expected Response:** *"I'm sorry, I cannot update shipping addresses directly for security reasons. Would you like me to transfer you to a human support agent?"*

---

## 📁 Repository Structure

```
voicebot-capstone/
├── backend/
│   ├── agent.py               # LiveKit Agent worker logic & pipeline
│   ├── server.py              # FastAPI token server & health endpoint
│   ├── stt_whisper.py         # Local Whisper STT wrapper
│   ├── tts_piper.py           # Local TTS audio synthesis wrapper
│   ├── tools/
│   │   ├── order_tools.py      # Order tracking logic (orders.json)
│   │   ├── product_tools.py    # Product catalog search (products.json)
│   │   └── faq_rag.py         # Local RAG search over policy docs
│   ├── data/
│   │   ├── orders.json        # Synthetic order data
│   │   ├── products.json      # Synthetic product data
│   │   └── faq/               # Markdown policy documents
│   ├── .env.example           # Environment template
│   └── requirements.txt       # Python dependencies
├── frontend/
│   ├── src/
│   │   ├── App.jsx            # Voice interface & LiveKit JS SDK integration
│   │   └── index.css          # Glassmorphism UI styling
│   └── package.json
├── TECHNICAL_REPORT.md        # Technical report & evaluation against rubric
└── README.md                  # Project documentation & run guide
```
