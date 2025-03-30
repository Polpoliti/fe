import streamlit as st
st.set_page_config(page_title="Finding Suitable Law", page_icon="⚖️", layout="wide")

import os
import torch

torch.classes.__path__ = []

from app_resources import model, pinecone_client, mongo_client
from openai import OpenAI
import json

# Set page config

# Disable parallelism in tokenizers to avoid warnings
os.environ["TOKENIZERS_PARALLELISM"] = "false"

# Constants
INDEX_NAME = "laws-names"
COLLECTION_NAME = "laws"
OPENAI_API_KEY = os.getenv("OPEN_AI")

# OpenAI Client
openai_client = OpenAI(api_key=OPENAI_API_KEY)

# MongoDB Collection
db = mongo_client[os.getenv("DATABASE_NAME")]
collection = db[COLLECTION_NAME]

# Pinecone Index
index = pinecone_client.Index(INDEX_NAME)

# === Styling ===
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

# === Load full details for a single law ===
def load_full_law_details(law_id):
    try:
        return collection.find_one({"IsraelLawID": law_id})
    except Exception as e:
        st.error(f"Error fetching full details for law ID {law_id}: {str(e)}")
        return None

# === Get GPT Explanation for Why the Law Helps ===
def get_law_explanation(scenario, law_doc):
    law_name = law_doc.get("Name", "")
    law_desc = law_doc.get("Description", "")
    prompt = f"""בהתבסס על הסצנריו הבא:
{scenario}

וכן על פרטי החוק הבא:
שם: {law_name}
תיאור: {law_desc}

אנא הסבר בצורה תמציתית ומקצועית מדוע חוק זה יכול לעזור למקרה זה, והערך אותו בסולם של 0 עד 10 כאשר 0 החוק לא יכול לעזור בכלל ולא קשור לנושא ו10 החוק מתאים כמו כפפה והוא בדיוק מה שהמשתמש תיאר והחוק יעזור לו למקרה, תהיה נוקשה בציון, אל תביא 9 לכל ציון, תהיה מגוון
החזר את התשובה בפורמט JSON בלבד, לדוגמה:
{{
  "advice": "הסבר תמציתי ומקצועי בעברית",
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
        return json.loads(output)
    except Exception as e:
        st.error(f"Error getting law explanation: {e}")
        return {"advice": "לא ניתן לקבל הסבר בשלב זה.", "score": "N/A"}

# === Main Interface ===
st.title("Finding Suitable Law")
scenario = st.text_area("Describe your scenario (what you plan to do, your situation, etc.):")

if st.button("Find Suitable Laws") and scenario:
    with st.spinner("Generating query embedding..."):
        query_embedding = model.encode([scenario], normalize_embeddings=True)[0]
    with st.spinner("Querying Pinecone for similar laws..."):
        query_response = index.query(
            vector=query_embedding.tolist(),
            top_k=5,
            include_metadata=True
        )
    if query_response and query_response.get("matches"):
        st.markdown("### Suitable Laws Found:")
        for match in query_response["matches"]:
            metadata = match.get("metadata", {})
            israel_law_id = metadata.get("IsraelLawID")
            if israel_law_id is None:
                continue
            law_doc = load_full_law_details(israel_law_id)
            if law_doc:
                name = law_doc.get("Name", "No Name")
                description = law_doc.get("Description", "אין תיאור לחוק זה")
                publication_date = law_doc.get("PublicationDate", "N/A")
                st.markdown(f"""
                    <div class="law-card">
                        <div class="law-title">{name} (ID: {israel_law_id})</div>
                        <div class="law-description">{description}</div>
                        <div class="law-meta">Publication Date: {publication_date}</div>
                    </div>
                """, unsafe_allow_html=True)
                with st.spinner("Getting site advice..."):
                    result = get_law_explanation(scenario, law_doc)
                    advice = result.get("advice", "")
                    score = result.get("score", "N/A")
                st.markdown(f"""
                    <div style="display: flex; justify-content: space-between; align-items: center;">
                        <span style="color: red;">עצת האתר: {advice}</span>
                        <span style="font-size: 24px; font-weight: bold; color: red;">{score}/10</span>
                    </div>
                """, unsafe_allow_html=True)
                if st.button(f"View Full Details for {israel_law_id}", key=f"details_{israel_law_id}"):
                    with st.spinner("Loading full details..."):
                        st.json(law_doc)
            else:
                st.warning(f"No document found for IsraelLawID: {israel_law_id}")
    else:
        st.info("No similar laws found.")
