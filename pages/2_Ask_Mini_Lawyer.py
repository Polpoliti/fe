import os
import streamlit as st
from openai import OpenAI
from dotenv import load_dotenv
from datetime import datetime
import pymongo
import socket

# Load environment variables
load_dotenv()

# MongoDB connection setup
MONGO_URI = os.getenv("MONGO_URI")
DATABASE_NAME = os.getenv("DATABASE_NAME")

client_mongo = pymongo.MongoClient(MONGO_URI)
db = client_mongo[DATABASE_NAME]
collection = db["conversations"]

# OpenAI API setup
client_openai = OpenAI(api_key=os.getenv("OPEN_AI"))

# Set page configuration
st.set_page_config(page_title="Ask Mini Lawyer", page_icon="💬", layout="wide")

# Custom CSS styling
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


# Functions
def get_user_ip():
    """Get the user's IP address."""
    try:
        host_name = socket.gethostname()
        user_ip = socket.gethostbyname(host_name)
        return user_ip
    except:
        return "unknown_ip"


def save_conversation(user_ip, user_name, messages):
    """Save messages to MongoDB for the user."""
    try:
        collection.update_one(
            {"user_ip": user_ip},
            {"$set": {"user_ip": user_ip, "user_name": user_name, "messages": messages}},
            upsert=True
        )
    except Exception as e:
        st.error(f"Error saving conversation: {e}")


def load_conversation(user_ip):
    """Load messages from MongoDB for the user."""
    try:
        conversation = collection.find_one({"user_ip": user_ip})
        if conversation:
            st.session_state['user_name'] = conversation['user_name']
            return conversation.get('messages', [])
        return []
    except Exception as e:
        st.error(f"Error loading conversation: {e}")
        return []


def delete_conversation(user_ip):
    """Delete the user's conversation document in MongoDB."""
    try:
        collection.delete_one({"user_ip": user_ip})
    except Exception as e:
        st.error(f"Error deleting conversation: {e}")


def generate_response(user_input):
    """Generate a GPT-4 response for the user input."""
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
    """Display chat messages."""
    for msg in st.session_state['messages']:
        role = "user-message" if msg['role'] == "user" else "bot-message"
        st.markdown(f"""
            <div class="{role}">
                {msg['content']}
                <div class="timestamp">{msg['timestamp']}</div>
            </div>
        """, unsafe_allow_html=True)


def add_message(role, content):
    """Add a new message to the session state."""
    st.session_state['messages'].append({
        "role": role,
        "content": content,
        "timestamp": datetime.now().strftime("%H:%M:%S")
    })


# AI System Prompt
PROMPT_TEMPLATE = """
You are a legal assistant specialized in Israeli law. Provide professional, accurate, and well-cited answers. 
Make sure your responses are clear and relevant ONLY to legal professionals and law students.
Answer always in Hebrew, and avoid using slang or informal language.
"""


# Main layout
st.markdown('<div class="chat-header">💬 Ask Mini Lawyer</div>', unsafe_allow_html=True)

# Check for user IP
user_ip = get_user_ip()

# Check for session states
if "user_name" not in st.session_state:
    st.session_state["user_name"] = None
if "messages" not in st.session_state:
    st.session_state["messages"] = load_conversation(user_ip)

if not st.session_state["user_name"]:
    with st.form(key="user_name_form", clear_on_submit=True):
        user_name_input = st.text_input("Please enter your name to start the chat:")
        submitted_name = st.form_submit_button("Start Chat")
    if submitted_name and user_name_input:
        st.session_state["user_name"] = user_name_input.strip()
        add_message("assistant", f"שלום {user_name_input}, איך אוכל לעזור לך היום?")
        save_conversation(user_ip, user_name_input, st.session_state['messages'])
        st.rerun()
else:
    # Chat container
    with st.container():
        st.markdown('<div class="chat-container">', unsafe_allow_html=True)
        display_messages()
        st.markdown('</div>', unsafe_allow_html=True)

    # User input section
    with st.form(key="chat_form", clear_on_submit=True):
        user_input = st.text_area("Ask your legal question here:", height=100)
        submitted = st.form_submit_button("Submit")

    if submitted and user_input.strip():
        add_message("user", user_input)  # Add user message immediately
        save_conversation(user_ip, st.session_state["user_name"], st.session_state['messages'])
        st.rerun()

    # Process GPT response if the last message is from the user
    if st.session_state['messages'] and st.session_state['messages'][-1]['role'] == "user":
        with st.spinner("Analyzing..."):
            assistant_response = generate_response(st.session_state['messages'][-1]['content'])
        add_message("assistant", assistant_response)
        save_conversation(user_ip, st.session_state["user_name"], st.session_state['messages'])
        st.rerun()

    # Clear chat confirmation
    if st.button("Clear Chat"):
        delete_conversation(user_ip)
        st.session_state['messages'] = []
        st.session_state['user_name'] = None
        st.rerun()

    # Footer
    st.markdown("""
        <div class="footer">
            <p><strong>Disclaimer:</strong> This AI assistant provides general legal information on Israeli law and does not substitute professional legal advice.</p>
        </div>
    """, unsafe_allow_html=True)
