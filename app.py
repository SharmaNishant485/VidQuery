import os
import tempfile

import streamlit as st
from dotenv import load_dotenv

from utils.audio_processor import process_input
from core.transcriber import transcribe_all
from core.summarizer import summarize, generate_title
from core.extractor import extract_action_items, extract_key_decisions, extract_questions
from core.rag_engine import build_rag_chain, ask_question

load_dotenv()

st.set_page_config(page_title="AI Video Assistant", page_icon="🎬", layout="wide")

# ---------------------------------------------------------------------------
# Session state setup
# ---------------------------------------------------------------------------
if "result" not in st.session_state:
    st.session_state.result = None
if "chat_history" not in st.session_state:
    st.session_state.chat_history = []  # list of (question, answer) tuples
if "processing" not in st.session_state:
    st.session_state.processing = False


def run_pipeline(source: str, language: str) -> dict:
    """Same pipeline as main.py, wired up for the Streamlit UI."""
    chunks = process_input(source)
    transcript = transcribe_all(chunks, language)
    title = generate_title(transcript)
    summary = summarize(transcript)
    action_items = extract_action_items(transcript)
    decisions = extract_key_decisions(transcript)
    questions = extract_questions(transcript)
    rag_chain = build_rag_chain(transcript)

    return {
        "title": title,
        "transcript": transcript,
        "summary": summary,
        "action_items": action_items,
        "key_decisions": decisions,
        "open_questions": questions,
        "rag_chain": rag_chain,
    }


def reset_session():
    st.session_state.result = None
    st.session_state.chat_history = []


# ---------------------------------------------------------------------------
# Sidebar — inputs
# ---------------------------------------------------------------------------
with st.sidebar:
    st.title("🎬 AI Video Assistant")
    st.caption("Turn any video into a transcript, summary, and a chatbot.")

    input_mode = st.radio("Video source", ["YouTube URL", "Upload a file"])

    source = None
    if input_mode == "YouTube URL":
        url = st.text_input("Paste a YouTube link", placeholder="https://youtube.com/watch?v=...")
        if url:
            source = url
    else:
        uploaded_file = st.file_uploader(
            "Upload an audio/video file", type=["mp4", "mp3", "wav", "m4a", "mkv"]
        )
        if uploaded_file is not None:
            suffix = os.path.splitext(uploaded_file.name)[1]
            tmp_dir = tempfile.gettempdir()
            tmp_path = os.path.join(tmp_dir, f"upload_{uploaded_file.name}")
            with open(tmp_path, "wb") as f:
                f.write(uploaded_file.getbuffer())
            source = tmp_path

    language = st.selectbox("Transcription language", ["english", "hinglish"])

    col1, col2 = st.columns(2)
    with col1:
        run_clicked = st.button("🚀 Process video", use_container_width=True, type="primary")
    with col2:
        st.button("🔄 Reset", use_container_width=True, on_click=reset_session)

    st.divider()
    st.caption(
        "Pipeline: download/extract audio → transcribe → summarize → "
        "extract insights → build a RAG chatbot over the transcript."
    )

# ---------------------------------------------------------------------------
# Run the pipeline
# ---------------------------------------------------------------------------
if run_clicked:
    if not source:
        st.sidebar.error("Please provide a YouTube URL or upload a file first.")
    else:
        reset_session()
        with st.spinner("Processing video — this can take a few minutes for longer videos..."):
            try:
                st.session_state.result = run_pipeline(source, language)
            except Exception as e:
                st.error(f"Something went wrong while processing the video:\n\n{e}")

# ---------------------------------------------------------------------------
# Main area — results
# ---------------------------------------------------------------------------
result = st.session_state.result

if result is None:
    st.info("👈 Add a YouTube link or upload a file, then click **Process video** to get started.")
else:
    st.header(f"📌 {result['title']}")

    tabs = st.tabs(
        ["📋 Summary", "✅ Action Items", "🔑 Key Decisions", "❓ Open Questions", "📝 Transcript", "💬 Chat"]
    )

    with tabs[0]:
        st.markdown(result["summary"])

    with tabs[1]:
        st.markdown(result["action_items"])

    with tabs[2]:
        st.markdown(result["key_decisions"])

    with tabs[3]:
        st.markdown(result["open_questions"])

    with tabs[4]:
        st.text_area("Full transcript", result["transcript"], height=400)
        st.download_button(
            "⬇️ Download transcript (.txt)",
            data=result["transcript"],
            file_name=f"{result['title']}_transcript.txt",
            mime="text/plain",
        )

    with tabs[5]:
        st.subheader("Chat with your video")

        # Render existing chat history
        for q, a in st.session_state.chat_history:
            with st.chat_message("user"):
                st.markdown(q)
            with st.chat_message("assistant"):
                st.markdown(a)

        question = st.chat_input("Ask something about the video...")
        if question:
            with st.chat_message("user"):
                st.markdown(question)
            with st.chat_message("assistant"):
                with st.spinner("Thinking..."):
                    try:
                        answer = ask_question(result["rag_chain"], question)
                    except Exception as e:
                        answer = f"Error while answering: {e}"
                st.markdown(answer)
            st.session_state.chat_history.append((question, answer))