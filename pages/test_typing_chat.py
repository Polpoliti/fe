import os
import streamlit as st
import torch
from openai import OpenAI
from dotenv import load_dotenv
from datetime import datetime
from app_resources import mongo_client
import uuid
from streamlit_js import st_js, st_js_blocking
from typing_indicator_realtime import show_typing_realtime 

# Fix for torch.classes error
torch.classes.__path__ = []
# Load environment variables
load_dotenv()

DATABASE_NAME = os.getenv("DATABASE_NAME")
collection = mongo_client[DATABASE_NAME]["conversations"]

client_openai = OpenAI(api_key=os.getenv("OPEN_AI"))

st.set_page_config(page_title="Ask Mini Lawyer", page_icon="💬", layout="wide")

st.markdown("""
    <style>
        .chat-container {
            background-color: #1E1E1E;
            padding: 20px;
            border-radius: 10px;
            box-shadow: 0px 4px 8px rgba(0, 0, 0, 0.2);
        }
        .chat-header {
            color: #4CAF50;
            font-size: 36px;
            font-weight: bold;
            text-align: center;
        }
        .user-message {
            background-color: #4CAF50;
            color: #ecf2f8;
            padding: 10px;
            border-radius: 10px;
            margin: 10px 20px;
            text-align: left;
            width: 60%;
        }
        .bot-message {
            background-color: #44475a;
            color: #ecf2f8;
            padding: 10px;
            border-radius: 10px;
            margin: 10px 20px;
            text-align: left;
            width: 60%;
        }
        .timestamp {
            font-size: 0.8em;
            color: #bbbbbb;
            margin-top: 5px;
        }
        .footer {
            text-align: center;
            color: #bbbbbb;
            font-size: 0.9em;
            margin-top: 20px;
        }
    </style>
""", unsafe_allow_html=True)

def get_localstorage_value(key: str):
    code = f"return localStorage.getItem('{key}');"
    return st_js_blocking(code, key="get_" + key)

def set_localstorage_value(key: str, value: str):
    code = f"localStorage.setItem('{key}', '{value}');"
    st_js(code)

def get_or_create_chat_id():
    if 'current_chat_id' not in st.session_state:
        st.session_state.current_chat_id = None

    chat_id = get_localstorage_value("MiniLawyerChatId")

    if chat_id in (None, "null"):
        if st.session_state.current_chat_id is None:
            new_id = str(uuid.uuid4())
            set_localstorage_value("MiniLawyerChatId", new_id)
            st.session_state.current_chat_id = new_id
            st.rerun()
        else:
            set_localstorage_value("MiniLawyerChatId", st.session_state.current_chat_id)
            return st.session_state.current_chat_id
    else:
        if st.session_state.current_chat_id != chat_id:
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
        st.error(f"Error saving conversation: {e}")

def load_conversation(local_storage_id):
    try:
        conversation = collection.find_one({"local_storage_id": local_storage_id})
        if conversation:
            st.session_state['user_name'] = conversation['user_name']
            return conversation.get('messages', [])
        return []
    except Exception as e:
        st.error(f"Error loading conversation: {e}")
        return []

def delete_conversation(local_storage_id):
    try:
        collection.delete_one({"local_storage_id": local_storage_id})
        st_js("localStorage.clear();")
        st.session_state.current_chat_id = None
    except Exception as e:
        st.error(f"Error deleting conversation: {e}")

def generate_response(user_input):
    try:
        messages = [{"role": "system", "content": PROMPT_TEMPLATE}]
        for msg in st.session_state['messages'][-5:]:
            messages.append({"role": msg['role'], "content": msg['content']})
        messages.append({"role": "user", "content": user_input})

        response = client_openai.chat.completions.create(
            model="gpt-4",
            messages=messages,
            max_tokens=700,
            temperature=0.7
        )
        return response.choices[0].message.content.strip()
    except Exception as e:
        return f"Error: {str(e)}"

def display_messages():
    for msg in st.session_state['messages']:
        role = "user-message" if msg['role'] == "user" else "bot-message"
        st.markdown(f"""
            <div class="{role}">
                {msg['content']}
                <div class="timestamp">{msg['timestamp']}</div>
            </div>
        """, unsafe_allow_html=True)

def add_message(role, content):
    st.session_state['messages'].append({
        "role": role,
        "content": content,
        "timestamp": datetime.now().strftime("%H:%M:%S")
    })

PROMPT_TEMPLATE = """
You are a legal assistant specialized in Israeli law. Provide professional, accurate, and well-cited answers. 
Make sure your responses are clear and relevant ONLY to legal professionals and law students.
Answer always in Hebrew, and avoid using slang or informal language.
"""

st.markdown('<div class="chat-header">💬 Ask Mini Lawyer</div>', unsafe_allow_html=True)

local_storage_id = get_or_create_chat_id()

if "user_name" not in st.session_state:
    st.session_state["user_name"] = None
if "messages" not in st.session_state:
    st.session_state["messages"] = load_conversation(local_storage_id)

if not st.session_state["user_name"]:
    with st.form(key="user_name_form", clear_on_submit=True):
        user_name_input = st.text_input("Please enter your name to start the chat:")
        submitted_name = st.form_submit_button("Start Chat")
    if submitted_name and user_name_input:
        st.session_state["user_name"] = user_name_input.strip()
        add_message("assistant", f"שלום {user_name_input}, איך אוכל לעזור לך היום?")
        save_conversation(local_storage_id, user_name_input, st.session_state['messages'])
        st.rerun()
else:
    with st.container():
        st.markdown('<div class="chat-container">', unsafe_allow_html=True)
        display_messages()
        st.markdown('</div>', unsafe_allow_html=True)

    with st.form(key="chat_form", clear_on_submit=True):
        user_input = st.text_area("Ask your legal question here:", height=100)
        submitted = st.form_submit_button("Submit")

    if submitted and user_input.strip():
        add_message("user", user_input)
        save_conversation(local_storage_id, st.session_state["user_name"], st.session_state['messages'])
        st.rerun()

    # ✅ שימוש באינדיקציה חדשה של "הבוט מקליד..."
    if st.session_state['messages'] and st.session_state['messages'][-1]['role'] == "user":
        typing_placeholder = show_typing_realtime()
        assistant_response = generate_response(st.session_state['messages'][-1]['content'])
        typing_placeholder.empty()
        add_message("assistant", assistant_response)
        save_conversation(local_storage_id, st.session_state["user_name"], st.session_state['messages'])
        st.rerun()

    if st.button("Clear Chat"):
        delete_conversation(local_storage_id)
        st.session_state['messages'] = []
        st.session_state['user_name'] = None
        st.rerun()

    st.markdown("""
        <div class="footer">
            <p><strong>Disclaimer:</strong> This AI assistant provides general legal information on Israeli law and does not substitute professional legal advice.</p>
        </div>
    """, unsafe_allow_html=True)
