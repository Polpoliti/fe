import os
import streamlit as st
import torch
from openai import OpenAI
from dotenv import load_dotenv
from datetime import datetime
from app_resources import mongo_client
import uuid
from streamlit_js import st_js, st_js_blocking

import fitz  # PyMuPDF
import docx
import sys
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

torch.classes.__path__ = []
load_dotenv()
client_openai = OpenAI(api_key=os.getenv("OPEN_AI"))
DATABASE_NAME = os.getenv("DATABASE_NAME")
collection = mongo_client[DATABASE_NAME]["conversations"]

st.set_page_config(page_title="Ask Mini Lawyer", page_icon="💬", layout="wide")

# ======================= סטייל =======================
st.markdown("""
<style>
    .chat-container {
        background-color: #1E1E1E; padding: 20px; border-radius: 10px; box-shadow: 0px 4px 8px rgba(0, 0, 0, 0.2);
    }
    .chat-header {
        color: #4CAF50; font-size: 36px; font-weight: bold; text-align: center;
    }
    .user-message {
        background-color: #4CAF50; color: #ecf2f8; padding: 10px; border-radius: 10px; margin: 10px 20px; text-align: left; width: 60%;
    }
    .bot-message {
        background-color: #44475a; color: #ecf2f8; padding: 10px; border-radius: 10px; margin: 10px 20px; text-align: left; width: 60%;
    }
    .timestamp {
        font-size: 0.8em; color: #bbbbbb; margin-top: 5px;
    }
    .footer {
        text-align: center; color: #bbbbbb; font-size: 0.9em; margin-top: 20px;
    }
</style>
""", unsafe_allow_html=True)

# ======================= פונקציות =======================
def get_localstorage_value(key): return st_js_blocking(f"return localStorage.getItem('{key}');", key="get_" + key)
def set_localstorage_value(key, value): st_js(f"localStorage.setItem('{key}', '{value}');")

def get_or_create_chat_id():
    if 'current_chat_id' not in st.session_state: st.session_state.current_chat_id = None
    chat_id = get_localstorage_value("MiniLawyerChatId")
    if chat_id in (None, "null"):
        new_id = str(uuid.uuid4())
        set_localstorage_value("MiniLawyerChatId", new_id)
        st.session_state.current_chat_id = new_id
        st.rerun()
    else:
        st.session_state.current_chat_id = chat_id
        return chat_id

def save_conversation(local_storage_id, user_name, messages):
    try:
        collection.update_one(
            {"local_storage_id": local_storage_id},
            {"$set": {"local_storage_id": local_storage_id, "user_name": user_name, "messages": messages}},
            upsert=True
        )
    except Exception as e:
        st.error(f"שגיאה בשמירת שיחה: {e}")

def load_conversation(local_storage_id):
    try:
        conversation = collection.find_one({"local_storage_id": local_storage_id})
        if conversation:
            st.session_state['user_name'] = conversation['user_name']
            return conversation.get('messages', [])
        return []
    except Exception as e:
        st.error(f"שגיאה בטעינה: {e}")
        return []

def delete_conversation(local_storage_id):
    try:
        collection.delete_one({"local_storage_id": local_storage_id})
        st_js("localStorage.clear();")
        st.session_state.current_chat_id = None
    except Exception as e:
        st.error(f"שגיאה במחיקת שיחה: {e}")

def read_pdf(file):
    text = ""
    with fitz.open(stream=file.read(), filetype="pdf") as doc:
        for page in doc:
            text += page.get_text()
    return text

def read_docx(file):
    text = ""
    doc = docx.Document(file)
    for para in doc.paragraphs:
        text += para.text + "\n"
    return text

def show_typing_realtime(message="🤖 הבוט מקליד..."):
    placeholder = st.empty()
    placeholder.markdown(f"<div style='color:gray; font-style:italic;'>{message}</div>", unsafe_allow_html=True)
    return placeholder

def format_professional_response(text):
    return f"""### ⚖️ תשובה משפטית:

{text.strip()}

---

*הבהרה: מענה זה מהווה מידע משפטי כללי ואינו מחליף ייעוץ משפטי.*
"""

def format_contract_summary(summary_text):
    return f"""### 🧾 סיכום מקצועי של המסמך:

{summary_text.strip()}

---

*הסיכום נערך אוטומטית ואינו מחליף בדיקה פרטנית של עורך דין.*
"""

def add_message(role, content):
    st.session_state['messages'].append({
        "role": role, "content": content, "timestamp": datetime.now().strftime("%H:%M:%S")
    })

def generate_response(user_input):
    try:
        context = f"""
        אתה עוזר משפטי מקצועי בדין הישראלי. 
        ענה בקצרה, בעברית משפטית מקצועית, תוך שמירה על דיוק וניסוח תקין.
        {"המסמך מסוכם כך: " + st.session_state['doc_summary'] if "doc_summary" in st.session_state else ""}
        """
        messages = [{"role": "system", "content": context}]
        for msg in st.session_state['messages'][-5:]:
            messages.append({"role": msg['role'], "content": msg['content']})
        messages.append({"role": "user", "content": user_input})
        response = client_openai.chat.completions.create(
            model="gpt-4", messages=messages, max_tokens=700, temperature=0.7
        )
        return response.choices[0].message.content.strip()
    except Exception as e:
        return f"שגיאה: {str(e)}"

# ======================= ריצה =======================

PROMPT_TEMPLATE = "הנחיה כללית לעוזר משפטי – לא בשימוש כי נשלח context דינאמי."

st.markdown('<div class="chat-header">💬 Ask Mini Lawyer</div>', unsafe_allow_html=True)
local_storage_id = get_or_create_chat_id()

if "user_name" not in st.session_state:
    st.session_state["user_name"] = None
if "messages" not in st.session_state:
    st.session_state["messages"] = load_conversation(local_storage_id)

# התחברות
if not st.session_state["user_name"]:
    with st.form(key="user_name_form", clear_on_submit=True):
        user_name_input = st.text_input("הכנס שם להתחלת שיחה:")
        submitted_name = st.form_submit_button("התחל שיחה")
    if submitted_name and user_name_input:
        st.session_state["user_name"] = user_name_input.strip()
        add_message("assistant", f"שלום {user_name_input}, איך אפשר לעזור?")
        save_conversation(local_storage_id, user_name_input, st.session_state['messages'])
        st.rerun()

# ממשק מלא
else:
    with st.container():
        st.markdown('<div class="chat-container">', unsafe_allow_html=True)
        display_messages()
        st.markdown('</div>', unsafe_allow_html=True)

    uploaded_file = st.file_uploader("📄 העלה מסמך משפטי לניתוח", type=["pdf", "docx"])
    if uploaded_file:
        if uploaded_file.type == "application/pdf":
            file_text = read_pdf(uploaded_file)
        elif uploaded_file.type in ["application/vnd.openxmlformats-officedocument.wordprocessingml.document", "application/msword"]:
            file_text = read_docx(uploaded_file)
        else:
            file_text = ""
        if file_text:
            st.session_state["uploaded_doc_text"] = file_text
            st.success("הקובץ הועלה ונקרא בהצלחה!")

    if "uploaded_doc_text" in st.session_state:
        if st.button("📋 סכם את המסמך"):
            with st.spinner("GPT מסכם את המסמך..."):
                summary_prompt = f"""
                סכם עבורי את המסמך המשפטי הבא. הסבר מהו נושא המסמך, האם הוא חוזה / כתב תביעה / החלטה, ואילו סעיפים עיקריים בולטים בו.
                ציין נקודות שראוי לשים לב אליהן. סכם בעברית משפטית מקצועית ובאופן תמציתי:
                ---
                {st.session_state['uploaded_doc_text']}
                """
                try:
                    response = client_openai.chat.completions.create(
                        model="gpt-4",
                        messages=[{"role": "user", "content": summary_prompt}],
                        temperature=0.5
                    )
                    doc_summary = response.choices[0].message.content.strip()
                    st.session_state["doc_summary"] = doc_summary
                except Exception as e:
                    st.error(f"שגיאה בקבלת סיכום: {e}")

        if "doc_summary" in st.session_state:
            formatted_summary = format_contract_summary(st.session_state["doc_summary"])
            st.markdown(formatted_summary, unsafe_allow_html=True)

    with st.form(key="chat_form", clear_on_submit=True):
        user_input = st.text_area("הכנס שאלה משפטית או שאלה על המסמך שהועלה", height=100)
        submitted = st.form_submit_button("שלח שאלה")

    if submitted and user_input.strip():
        final_input = user_input
        if "uploaded_doc_text" in st.session_state:
            final_input = f"""
            שאלה על מסמך:
            {st.session_state['uploaded_doc_text']}

            השאלה היא:
            {user_input}
            """
        add_message("user", user_input)
        save_conversation(local_storage_id, st.session_state["user_name"], st.session_state['messages'])
        st.rerun()

    if st.session_state['messages'] and st.session_state['messages'][-1]['role'] == "user":
        typing_placeholder = show_typing_realtime()
        assistant_response = generate_response(st.session_state['messages'][-1]['content'])
        typing_placeholder.empty()
        formatted_response = format_professional_response(assistant_response)
        add_message("assistant", formatted_response)
        save_conversation(local_storage_id, st.session_state["user_name"], st.session_state['messages'])
        st.rerun()

    if st.button("🗑 נקה שיחה"):
        delete_conversation(local_storage_id)
        st.session_state['messages'] = []
        st.session_state['user_name'] = None
        st.rerun()

    st.markdown("""
        <div class="footer">
            <p><strong>הבהרה:</strong> מדובר בסיוע משפטי כללי בלבד ואינו מחליף ייעוץ מקצועי מעורך דין.</p>
        </div>
    """, unsafe_allow_html=True)
