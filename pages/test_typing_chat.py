import streamlit as st
from typing_indicator_realtime import show_typing_realtime
import time

st.set_page_config(page_title="🔁 בדיקת Typing Indicator", layout="wide")

st.title("🤖 בדיקת הבוט מקליד...")

if "messages" not in st.session_state:
    st.session_state.messages = []

# תיבת קלט
user_input = st.text_input("כתוב שאלה משפטית כלשהי:")

# כשמגישים
if st.button("שלח שאלה"):
    st.session_state.messages.append(("🧑", user_input))

    # הצג typing
    typing_placeholder = show_typing_realtime()

    # סימולציית המתנה כמו GPT
    time.sleep(2)

    # מחק את ההודעה הזמנית
    typing_placeholder.empty()

    # הוסף תשובה מזויפת
    st.session_state.messages.append(("🤖", "זו תשובה לדוגמה מהבוט"))

# הצגת שיחה
for sender, msg in st.session_state.messages:
    st.markdown(f"**{sender}**: {msg}")
