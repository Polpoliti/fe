import streamlit as st

st.set_page_config(page_title="Mini Lawyer - Judgments", page_icon="📜", layout="wide")

from app_resources import mongo_client
from dotenv import load_dotenv
import os
from datetime import datetime

# Load environment variables
load_dotenv()

# Database details
MONGO_URI = os.getenv('MONGO_URI')
DATABASE_NAME = os.getenv('DATABASE_NAME')
COLLECTION_NAME = "judgments"


# Custom CSS for Styling
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
        .pagination-controls {
            margin-top: 20px;
            text-align: center;
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


# Initialize MongoDB connection

# Query distinct ProcedureType values
def get_procedure_types(client):
    try:
        db = client[DATABASE_NAME]
        collection = db[COLLECTION_NAME]
        procedure_types = collection.distinct("ProcedureType")
        return sorted(procedure_types)
    except Exception as e:
        st.error(f"Error fetching ProcedureType values: {str(e)}")
        return []


# Query judgments with pagination and filtering
def query_judgments(client, filters=None, skip=0, limit=10):
    try:
        db = client[DATABASE_NAME]
        collection = db[COLLECTION_NAME]
        pipeline = []

        if filters:
            pipeline.append({"$match": filters})

        pipeline.append({"$sort": {"CaseNumber": 1}})
        pipeline.append({"$skip": skip})
        pipeline.append({"$limit": limit})

        judgments = list(collection.aggregate(pipeline))
        return judgments
    except Exception as e:
        st.error(f"Error querying judgments: {str(e)}")
        return []


# Count total judgments with filters
def count_judgments(client, filters=None):
    try:
        db = client[DATABASE_NAME]
        collection = db[COLLECTION_NAME]
        if filters:
            return collection.count_documents(filters)
        return collection.estimated_document_count()
    except Exception as e:
        st.error(f"Error counting judgments: {str(e)}")
        return 0


def main():
    st.title("📜 Judgments Searching")

    # Initialize pagination state
    if "page" not in st.session_state:
        st.session_state["page"] = 1

    # Connect to MongoDB
    client = mongo_client

    with st.spinner("Loading filters..."):
        procedure_types = get_procedure_types(client)
        procedure_types = [x for x in procedure_types if x not in {'', ', , , , ', ' ,בג"ץ', 'בג"ץ, '}]

    # Filters section
    with st.expander("Filters"):
        case_number = st.text_input("Filter by Case Number (Regex)", key="case_number_filter")
        judgments_name = st.text_input("Filter by Name (Regex)", key="judgments_name_filter")
        procedure_type = st.selectbox("Filter by Procedure Type", options=["All"] + procedure_types,
                                      key="procedure_type_filter")
        date_range = st.date_input("Filter by Publication Date Range", [])

    # Pagination state
    page = st.session_state["page"]
    page_size = 10
    skip = (page - 1) * page_size

    # Build filters based on input
    filters = {}
    if case_number:
        filters["CaseNumber"] = {"$regex": case_number, "$options": "i"}
    if judgments_name:
        filters["Name"] = {"$regex": judgments_name, "$options": "i"}
    if procedure_type != "All":
        filters["ProcedureType"] = procedure_type
    if len(date_range) == 2:
        start_date, end_date = date_range
        filters["PublicationDate"] = {
            "$gte": datetime.combine(start_date, datetime.min.time()),
            "$lte": datetime.combine(end_date, datetime.max.time())
        }

    # Query judgments
    with st.spinner("Loading Judgments..."):
        judgments = query_judgments(client, filters, skip, page_size)
        total_judgments = count_judgments(client, filters)

    if judgments:
        st.markdown(f"### Page {page} (Showing {len(judgments)} of {total_judgments} judgments)")
        for judgment in judgments:
            judgment_description = judgment.get("Description", "").strip() or "אין תיאור לפסק הדין זה"
            with st.container():
                st.markdown(f"""
                    <div class="law-card">
                        <div class="law-title">{judgment['Name']} (ID: {judgment['CaseNumber']})</div>
                        <div class="law-description">{judgment_description}</div>
                        <div class="law-meta">Publication Date: {judgment.get('DecisionDate', 'N/A')}</div>
                        <div class="law-meta">Procedure Type: {judgment.get('ProcedureType', 'N/A')}</div>
                    </div>
                """, unsafe_allow_html=True)

                col1, col2 = st.columns([1, 1])
                with col1:
                    if st.button(f"View Full Details for {judgment['CaseNumber']}",
                                 key=f"details_{judgment['CaseNumber']}"):
                        st.json(judgment)
                with col2:
                    documents = judgment.get('Documents', [])
                    if documents and isinstance(documents, list) and 'url' in documents[0]:
                        document_url = documents[0]['url']
                        st.markdown(
                            f"""
                            <a href="{document_url}" target="_blank" style="text-decoration:none;">
                                <button style="
                                    background-color:#7ce38b;
                                    color:white;
                                    border:none;
                                    padding:8px 16px;
                                    border-radius:5px;
                                    cursor:pointer;
                                    font-size:14px;">
                                    Download Judgment
                                </button>
                            </a>
                            """,
                            unsafe_allow_html=True
                        )

        total_pages = (total_judgments + page_size - 1) // page_size
        col1, col2, col3 = st.columns(3)
        with col1:
            if st.button("Previous Page") and page > 1:
                st.session_state["page"] -= 1
        with col2:
            st.write(f"Page {page} of {total_pages}")
        with col3:
            if st.button("Next Page") and page < total_pages:
                st.session_state["page"] += 1
    else:
        st.warning("No judgments found with the applied filters.")



if __name__ == "__main__":
    main()
