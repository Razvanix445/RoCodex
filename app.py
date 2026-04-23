import os
import random
import streamlit as st
from rag import answer as rag_answer

st.set_page_config(
    page_title="RoCodex",
    page_icon="⚖️",
    layout="centered",
)

GROQ_API_KEY = os.environ.get("GROQ_API_KEY", "")
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

with open(os.path.join(BASE_DIR, "app_logo.svg"), "r", encoding="utf-8") as f:
    LOGO_SVG = f.read()

import base64
LOGO_B64 = base64.b64encode(LOGO_SVG.encode()).decode()
LOGO_URI = f"data:image/svg+xml;base64,{LOGO_B64}"

WELCOME_MESSAGES = [
    "Bine ai venit! Pune orice întrebare despre legislația română.",
    "Salut! Sunt aici să te ajut să înțelegi legile din România.",
    "Salut! Întreabă-mă orice despre drepturile tale legale.",
    "Salut! Explorează legislația română cu ajutorul meu.",
]

EXAMPLES = [
    "Ce drepturi are un salariat la concediu de odihnă?",
    "Care sunt obligațiile angajatorului față de salariat?",
    "Ce este prezumția de nevinovăție?",
    "Cum se calculează indemnizația de concediu?",
]

st.markdown(f"""
<style>
#MainMenu {{ visibility: hidden; }}
footer    {{ visibility: hidden; }}
/* ── Hero ── */
.hero-wrap {{
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    min-height: 58vh;
    text-align: center;
    gap: 0.6rem;
    padding-bottom: 1.5rem;
}}
.hero-logo img {{
    width: 130px;
    height: 130px;
    margin-bottom: 0.4rem;
    filter: drop-shadow(0 4px 12px rgba(30,58,95,0.25));
}}
.hero-title {{
    font-size: 2.8rem;
    font-weight: 800;
    color: #1e3a5f;
    letter-spacing: -0.02em;
    margin: 0;
}}
.hero-subtitle {{
    font-size: 1.05rem;
    color: #64748b;
}}
.hero-welcome {{
    font-size: 1.8rem;
    color: #DDE4ED;
    font-weight: 700;
    font-style: normal;
}}
/* ── Assistant avatar: replace default icon with our SVG ── */
/* Streamlit renders the avatar in [data-testid="chatAvatarIcon-assistant"] */
[data-testid="chatAvatarIcon-assistant"] {{
    background: url("{LOGO_URI}") center/cover no-repeat !important;
    border-radius: 4px !important;
}}
/* Hide the default text/emoji inside the avatar container */
[data-testid="chatAvatarIcon-assistant"] svg,
[data-testid="chatAvatarIcon-assistant"] p {{
    display: none !important;
}}
/* ── User bubble: push to right side ── */
[data-testid="stChatMessageContent-user"] {{
    margin-left: auto !important;
    background: #1e3a5f !important;
    color: #ffffff !important;
    border-radius: 18px 18px 4px 18px !important;
}}
/* User text color override */
[data-testid="stChatMessageContent-user"] p {{
    color: #ffffff !important;
}}
/* User avatar: right side */
[data-testid="stChatMessage-user"] {{
    flex-direction: row-reverse !important;
}}
[data-testid="chatAvatarIcon-user"] {{
    background: #1e3a5f !important;
    color: #fcd34d !important;
    font-weight: 700 !important;
    font-size: 0.75rem !important;
}}
/* ── Assistant bubble ── */
[data-testid="stChatMessageContent-assistant"] {{
    background: #f1f5f9 !important;
    border-radius: 18px 18px 18px 4px !important;
}}
/* ── Sidebar logo ── */
.sidebar-logo {{
    display: flex;
    align-items: center;
    gap: 0.6rem;
    margin-bottom: 0.25rem;
}}
.sidebar-logo img {{
    width: 36px;
    height: 36px;
}}
.sidebar-logo span {{
    font-size: 1.3rem;
    font-weight: 800;
    color: #1e3a5f;
    letter-spacing: -0.01em;
}}
</style>
""", unsafe_allow_html=True)

with st.sidebar:
    st.markdown(f"""
    <div style="text-align: center; padding: 0 0 0;">
        <img src="{LOGO_URI}" alt="RoCodex logo" style="width: 80px; height: 80px;"/>
        <div style="font-size: 1.8rem; font-weight: 800; color: #1e3a5f; letter-spacing: -0.01em; margin-top: 0.4rem;">RoCodex</div>
    </div>
    """, unsafe_allow_html=True)
    st.divider()

    api_key = st.text_input(
        "🔑 Groq API Key",
        value=GROQ_API_KEY,
        type="password",
        placeholder="gsk_...",
        help="Cheie gratuită la console.groq.com",
    )
    st.caption("Cheia nu este salvată nicăieri.")
    st.divider()

    st.markdown("""
**Legislație acoperită:**
- 📋 Codul Muncii
- 📋 Codul Civil
- ⚖️ Codul Penal
- 🏛️ Cod Procedură Civilă
- 🏛️ Cod Procedură Penală
- 🏢 Legea Societăților
""")
    st.divider()
    st.caption(
        "⚠️ RoCodex oferă informații juridice generale. "
        "Nu constituie consultanță juridică. "
        "Consultați un avocat pentru situații specifice."
    )

if "messages" not in st.session_state:
    st.session_state.messages = []

if "welcome_msg" not in st.session_state:
    st.session_state.welcome_msg = random.choice(WELCOME_MESSAGES)

def render_assistant(content: str, sources: list):
    st.markdown(content)
    if sources:
        with st.expander("📚 Surse folosite", expanded=False):
            for i, src in enumerate(sources, 1):
                score_pct = int(src["score"] * 100)
                st.markdown(
                    f"**[{i}] {src['law_title']} — {src['article_number']}** "
                    f"`{score_pct}% relevanță`"
                )
                st.caption(
                    src["text"][:300] + ("…" if len(src["text"]) > 300 else "")
                )
                if i < len(sources):
                    st.divider()

if not st.session_state.messages:
    st.markdown(f"""
    <div class="hero-wrap">
        <div class="hero-logo">
            <img src="{LOGO_URI}" alt="RoCodex"/>
        </div>
        <div class="hero-title">RoCodex</div>
        <div class="hero-subtitle">Asistent juridic bazat pe legislația română</div>
        <div class="hero-welcome">{st.session_state.welcome_msg}</div>
    </div>
    """, unsafe_allow_html=True)

    st.markdown("**Încearcă una din întrebările de mai jos:**")
    cols = st.columns(2)
    for i, example in enumerate(EXAMPLES):
        with cols[i % 2]:
            if st.button(example, key=f"ex_{i}", use_container_width=True):
                st.session_state.prefill = example
                st.rerun()

else:
    for msg in st.session_state.messages:
        if msg["role"] == "user":
            with st.chat_message("user"):
                st.markdown(msg["content"])
        else:
            with st.chat_message("assistant"):
                render_assistant(msg["content"], msg.get("sources", []))

prefill_value = st.session_state.pop("prefill", "")
user_input = st.chat_input("Scrie întrebarea ta juridică...")
question = user_input or prefill_value

if question:
    question = question.strip()

    st.session_state.messages.append({
        "role": "user", "content": question, "sources": None
    })

    key = api_key.strip() if api_key.strip() else GROQ_API_KEY
    if not key:
        st.session_state.messages.append({
            "role": "assistant",
            "content": "⚠️ Lipsește Groq API key. Introdu cheia în sidebar.",
            "sources": [],
        })
        st.rerun()

    with st.spinner("Caut în legislație..."):
        try:
            result = rag_answer(question, groq_api_key=key)
            reply = result["answer"]
            sources = result["sources"]
        except Exception as e:
            reply = f"Eroare: {e}"
            sources = []

    st.session_state.messages.append({
        "role": "assistant",
        "content": reply,
        "sources": sources,
    })
    st.rerun()