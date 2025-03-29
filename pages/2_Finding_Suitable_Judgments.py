import os
import torch

# Fix for torch.classes error
torch.classes.__path__ = []

import streamlit as st

st.set_page_config(page_title="Finding Suitable Judgments", page_icon="📜", layout="wide")
# If set_page_config is already set by a parent app, the above call will be ignored.

import pinecone
from sentence_transformers import SentenceTransformer
from pymongo import MongoClient
from dotenv import load_dotenv
from datetime import datetime
import openai
import json

# Disable parallelism in tokenizers to avoid warnings
os.environ["TOKENIZERS_PARALLELISM"] = "false"

# === Load Environment Variables ===
load_dotenv()

PINECONE_API_KEY = os.getenv("PINECONE_API_KEY")
OPENAI_API_KEY = os.getenv("OPEN_AI")
# Use a separate index for judgments
INDEX_NAME = "judgments-names"

MONGO_URI = os.getenv("MONGO_URI")
DATABASE_NAME = os.getenv("DATABASE_NAME")
COLLECTION_NAME = "judgments"

st.markdown("""
    <style>
        .law-card {
            border: 1px solid #e0e0e0;
            border-radius: 10px;
            padding: 20px;
            margin-bottom: 15px;
            box-shadow: 0px 2px 4px rgba(0,0,0,0.1);
            background-color: #f9f9f9;
        }
        .law-title {
            font-size: 20px;
            font-weight: bold;
            color: #333;
        }
        .law-description {
            font-size: 16px;
            color: #444;
            margin: 10px 0;
        }
        .law-meta {
            font-size: 14px;
            color: #555;
        }
        .stButton>button {
            background-color: #7ce38b;
            color: white;
            font-size: 14px;
            border: none;
            padding: 8px 16px;
            border-radius: 5px;
            cursor: pointer;
        }
        .stButton>button:hover {
            background-color: #7ce38b;
        }
    </style>
""", unsafe_allow_html=True)

# === Initialize Pinecone Client ===
if not PINECONE_API_KEY:
    st.error("Pinecone API key not found in environment variables.")
    st.stop()

pc = pinecone.Pinecone(api_key=PINECONE_API_KEY)
st.info("Pinecone client initialized.")
index = pc.Index(INDEX_NAME)

# === Load Embedding Model ===
st.info("Loading embedding model...")
model = SentenceTransformer("intfloat/multilingual-e5-large")
st.success("Embedding model loaded successfully.")

# === Initialize OpenAI Client using new interface ===
openai_client = openai.OpenAI(api_key=OPENAI_API_KEY)

# === Connect to MongoDB ===
try:
    mongo_client = MongoClient(MONGO_URI)
    db = mongo_client[DATABASE_NAME]
    collection = db[COLLECTION_NAME]
    st.info(f"Connected to MongoDB collection: {COLLECTION_NAME}")
except Exception as e:
    st.error(f"Failed to connect to MongoDB: {e}")
    st.stop()


# === Load full details for a single judgment ===
def load_full_judgment_details(client, case_number):
    try:
        db = client[DATABASE_NAME]
        collection = db[COLLECTION_NAME]
        judgment = collection.find_one({"CaseNumber": case_number})
        return judgment
    except Exception as e:
        st.error(f"Error fetching full details for CaseNumber {case_number}: {str(e)}")
        return None


# === Get GPT Explanation for Why the Judgment Helps ===
def get_judgment_explanation(scenario, judgment_doc):
    judgment_name = judgment_doc.get("Name", "")
    judgment_desc = judgment_doc.get("Description", "")
    prompt = f"""בהתבסס על הסצנריו הבא:
{scenario}

וכן על פרטי פסק הדין הבא:
שם: {judgment_name}
תיאור: {judgment_desc}

אנא הסבר בצורה תמציתית ומקצועית מדוע פסק דין זה יכול לעזור למקרה זה, והערך אותו בסולם של 0 עד 10 כאשר 0 - אינו עוזר כלל ו-10 - מתאים במדויק.
החזר את התשובה בפורמט JSON בלבד, לדוגמה:
{{
  "advice": "הסבר מקצועי בעברית",
  "score": 8
}}
אין להוסיף טקסט נוסף.
"""
    try:
        response = openai_client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.7
        )
        output = response.choices[0].message.content.strip()
        result = json.loads(output)
        return result
    except Exception as e:
        st.error(f"Error getting judgment explanation: {e}")
        return {"advice": "לא ניתן לקבל הסבר בשלב זה.", "score": "N/A"}


# === UI: Ask for User Scenario ===
st.title("Finding Suitable Judgments")
scenario = st.text_area("Describe your scenario (what you plan to do, your situation, etc.):")

if st.button("Find Suitable Judgments") and scenario:
    with st.spinner("Generating query embedding..."):
        query_embedding = model.encode([scenario], normalize_embeddings=True)[0]
    with st.spinner("Querying Pinecone for similar judgments..."):
        query_response = index.query(
            vector=query_embedding.tolist(),
            top_k=5,
            include_metadata=True
        )
    if query_response and query_response.get("matches"):
        st.markdown("### Suitable Judgments Found:")
        for match in query_response["matches"]:
            metadata = match.get("metadata", {})
            case_number = metadata.get("CaseNumber")
            if case_number is None:
                continue
            judgment_doc = load_full_judgment_details(mongo_client, case_number)
            if judgment_doc:
                name = judgment_doc.get("Name", "No Name")
                description = judgment_doc.get("Description", "אין תיאור לפסק הדין זה")
                decision_date = judgment_doc.get("DecisionDate", "N/A")
                procedure_type = judgment_doc.get("ProcedureType", "N/A")
                st.markdown(f"""
                    <div class="law-card">
                        <div class="law-title">{name} (ID: {case_number})</div>
                        <div class="law-description">{description}</div>
                        <div class="law-meta">Decision Date: {decision_date}</div>
                        <div class="law-meta">Procedure Type: {procedure_type}</div>
                    </div>
                """, unsafe_allow_html=True)
                with st.spinner("Getting site advice..."):
                    result = get_judgment_explanation(scenario, judgment_doc)
                    advice = result.get("advice", "")
                    score = result.get("score", "N/A")
                st.markdown(f"""
                    <div style="display: flex; justify-content: space-between; align-items: center;">
                        <span style="color: red;">עצת האתר: {advice}</span>
                        <span style="font-size: 24px; font-weight: bold; color: red;">{score}/10</span>
                    </div>
                """, unsafe_allow_html=True)
                if st.button(f"View Full Details for {case_number}", key=f"details_{case_number}"):
                    with st.spinner("Loading full details..."):
                        st.json(judgment_doc)
            else:
                st.warning(f"No document found for CaseNumber: {case_number}")
    else:
        st.info("No similar judgments found.")
