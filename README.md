Create the dataset by scraping:
`del data\laws.jsonl`
`del data\articles.jsonl`
`python pipeline.py --ids 65851 53158 7816 35684`
`python ../inspect.py`

`streamlit run app.py`



# RoCodex — Romanian Legal Assistant

[![Python](https://img.shields.io/badge/Python-3776AB?style=for-the-badge&logo=python&logoColor=white)](https://python.org/)
[![Streamlit](https://img.shields.io/badge/Streamlit-FF4B4B?style=for-the-badge&logo=streamlit&logoColor=white)](https://streamlit.io/)
[![Groq](https://img.shields.io/badge/Groq-F55036?style=for-the-badge&logo=groq&logoColor=white)](https://groq.com/)
[![FAISS](https://img.shields.io/badge/FAISS-0467DF?style=for-the-badge&logo=meta&logoColor=white)](https://faiss.ai/)
[![HuggingFace](https://img.shields.io/badge/🤗%20Hugging%20Face-FFD21E?style=for-the-badge)](https://huggingface.co/)

> Ask questions about Romanian law and get cited, sourced answers backed by real legal articles.

RoCodex is a **RAG-powered** (Retrieval-Augmented Generation) legal assistant that scrapes Romanian legislation directly from the official government portal, `legislatie.just.ro`, indexes it using semantic vector search, and answers questions by retrieving the most relevant law articles and passing them to an LLM. The AI never answers from memory. Every response is grounded in real, retrieved legal text.

---

## 🌟 Features

### ⚖️ **Legal Intelligence**
- **Cited answers** — every response references the exact law and article number used
- **Source transparency** — collapsible source panel shows which articles were retrieved and their relevance scores
- **Fallback** — if no relevant articles are found, the assistant says so instead of hallucinating
- **Romanian-first** — multilingual embedding model with native Romanian language support

### 🔍 **Semantic Search**
- **Meaning-based retrieval** — finds relevant articles even when the question uses different words than the law
- **FAISS vector index** — sub-second search across thousands of law articles
- **Cosine similarity scoring** — ranked results by semantic relevance, not just keyword matching

### 🏛️ **Legal Coverage**
- 📋 Codul Muncii (Labour Code)
- 📋 Codul Civil (Civil Code)
- ⚖️ Codul Penal (Criminal Code)
- 🏛️ Cod Procedură Civilă (Civil Procedure Code)
- 🏛️ Cod Procedură Penală (Criminal Procedure Code)
- 🏢 Legea Societăților (Company Law)

### 🤖 **AI Generation**
- **Llama 3.3 70B** via Groq
- **Low temperature (0.1)** — deterministic answers instead of creative ones
- **Strict system prompt** — the model is instructed to use only the retrieved articles

---

## 🔬 Technical Specifications

### 🧠 **Embedding Model**

| Component | Details |
|---|---|
| **Model** | `paraphrase-multilingual-MiniLM-L12-v2` |
| **Provider** | Sentence Transformers / Hugging Face |
| **Vector Dimensions** | 384 |
| **Similarity Metric** | Cosine similarity (Inner Product on normalized vectors) |
| **Languages** | 50+ languages including Romanian |
| **Model Size** | ~120MB (cached after first run) |

### 🔎 **Retrieval**

| Component | Details |
|---|---|
| **Index Type** | FAISS `IndexFlatIP` (exact search) |
| **Top-K** | 5 articles per query |
| **Normalization** | L2-normalized embeddings for unit-length cosine similarity |
| **Score Range** | 0.0 – 1.0 (higher = more relevant) |

### 🤖 **Generation**

| Component | Details |
|---|---|
| **Model** | `llama-3.3-70b-versatile` |
| **Provider** | Groq (free tier) |
| **Temperature** | 0.1 |
| **Max Tokens** | 1024 |
| **Prompt Style** | System prompt + user context window with retrieved articles |

### 🔧 **Technical Stack**

#### **Scraping & Data**
```
HTTP Requests:     requests
HTML Parsing:      beautifulsoup4
SOAP API Client:   suds-community
Encoding Fix:      ftfy
Progress Bars:     tqdm
```

#### **NLP & Search**
```
Embeddings:        sentence-transformers
Vector Index:      faiss-cpu
Numerics:          numpy
```

#### **AI Generation**
```
LLM Provider:      groq
Model:             llama-3.3-70b-versatile
```

#### **Web App**
```
Framework:         streamlit
```

---

## 🚀 Getting Started

### 📋 Prerequisites

- **Python 3.10+**
- **Groq API Key** — free at [console.groq.com](https://console.groq.com)

### 📦 Installation

```bash
git clone https://github.com/Razvanix445/RoCodex.git
cd RoCodex
pip install -r requirements.txt
```

### Step 1 — Build the Dataset

Scrape the laws you want to index. Specify IDs manually.

```bash
python pipeline.py --ids 41627 175630 109855
```

This produces `data/laws.jsonl` and `data/articles.jsonl`.

### Step 2 — Build the Vector Index

```bash
python indexer.py
```

This embeds all articles and produces `data/faiss.index` and `data/metadata.jsonl`. Takes a few minutes on first run (model download ~120MB).

### Step 3 — Run the App

```bash
streamlit run app.py
```

Open your browser at `http://localhost:8501`, enter your Groq API key in the sidebar, and start asking questions.

---

## 📊 Data Pipeline Details

### Text Cleaning (`cleaner.py`)

Romanian legal text from the portal requires specific cleaning:

| Problem | Solution |
|---|---|
| Legacy diacritics (`ş`, `ţ`) | Normalized to correct Unicode (`ș`, `ț`) |
| Encoding mojibake | Fixed with `ftfy` library |
| Site boilerplate (nav, footer) | Stripped with regex patterns |
| Amendment-only articles | Detected and filtered out (>50% amendment keywords) |
| Abrogated articles | Skipped if body is only "Abrogat" |
| Articles too short | Filtered if < 80 characters after cleaning |

### Article Chunking

Each article is stored as a `chunk` that includes its source context:

```
LEGE 53 2003
Articolul 145

Salariații au dreptul la concediu de odihnă anual plătit...
```
---

## ⚠️ Disclaimer

RoCodex provides general legal information based on official Romanian legislation. It does **not** constitute legal advice. Always consult a qualified lawyer for specific legal situations.
