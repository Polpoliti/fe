import streamlit as st
import pymongo
import requests
from io import BytesIO
from dotenv import load_dotenv
import os
from datetime import datetime

# Load environment variables
load_dotenv()

# Database details
MONGO_URI = os.getenv('MONGO_URI')
DATABASE_NAME = os.getenv('DATABASE_NAME')
COLLECTION_NAME = "judgments"

st.set_page_config(page_title="Mini Lawyer - Judgments", page_icon="📜", layout="wide")

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
        .law-meta {
            font-size: 14px;
            color: #555;
        }
        .law-actions {
            margin-top: 15px;
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
def init_connection():
    try:
        return pymongo.MongoClient(MONGO_URI)
    except Exception as e:
        st.error(f"Failed to connect to MongoDB: {str(e)}")
        return None


# Query distinct ProcedureType values
def get_procedure_types(client):
    try:
        db = client[DATABASE_NAME]
        collection = db[COLLECTION_NAME]
        procedure_types = collection.distinct("ProcedureType")
        return sorted(procedure_types)  # Sort the options alphabetically
    except Exception as e:
        st.error(f"Error fetching ProcedureType values: {str(e)}")
        return []


# Query laws with pagination and filtering
def query_laws(client, filters=None, skip=0, limit=10):
    try:
        db = client[DATABASE_NAME]
        collection = db[COLLECTION_NAME]
        pipeline = []

        # Apply filters
        if filters:
            pipeline.append({"$match": filters})

        # Sort by CaseNumber (or other criteria)
        pipeline.append({"$sort": {"CaseNumber": 1}})

        # Skip and limit for pagination
        pipeline.append({"$skip": skip})
        pipeline.append({"$limit": limit})

        laws = list(collection.aggregate(pipeline))
        return laws
    except Exception as e:
        st.error(f"Error querying laws: {str(e)}")
        return []


# Count total laws with filters
def count_laws(client, filters=None):
    try:
        db = client[DATABASE_NAME]
        collection = db[COLLECTION_NAME]
        if filters:
            return collection.count_documents(filters)
        return collection.estimated_document_count()
    except Exception as e:
        st.error(f"Error counting laws: {str(e)}")
        return 0


# Load full details for a single law
def load_full_law_details(client, case_number):
    try:
        db = client[DATABASE_NAME]
        collection = db[COLLECTION_NAME]
        law = collection.find_one({"CaseNumber": case_number})  # Fetch full details
        return law
    except Exception as e:
        st.error(f"Error fetching full details for CaseNumber {case_number}: {str(e)}")
        return None


# Function to reset page to 1
def reset_page():
    st.session_state["page"] = 1


# Function to download the file from a URL
def download_file(url):
    try:
        response = requests.get(url)
        if response.status_code == 200:
            return BytesIO(response.content)  # Return the file content as a BytesIO object
        else:
            st.error(f"Failed to download file: HTTP {response.status_code}")
            return None
    except Exception as e:
        st.error(f"Error downloading file: {str(e)}")
        return None


def main():
    st.title("📜 Judgments Searching")

    # Initialize pagination state
    if "page" not in st.session_state:
        st.session_state["page"] = 1

    # Connect to MongoDB and fetch ProcedureType options with a spinner
    client = init_connection()
    if not client:
        return

    with st.spinner("Loading filters..."):
        procedure_types = get_procedure_types(client)
        procedure_types = [x for x in procedure_types if x not in {'', ', , , , ', ' ,בג"ץ', 'בג"ץ, '}]  # Clean invalid ProcedureType values

    # Filters section
    with st.expander("Filters"):
        case_number = st.text_input(
            "Filter by Case Number (Regex)",
            key="case_number_filter",
            on_change=reset_page  # Reset page when this filter changes
        )
        judgments_name = st.text_input(
            "Filter by Name (Regex)",
            key="judgments_name_filter",
            on_change=reset_page  # Reset page when this filter changes
        )
        procedure_type = st.selectbox(
            "Filter by Procedure Type",
            options=["All"] + procedure_types,
            key="procedure_type_filter",
            on_change=reset_page  # Reset page when this filter changes
        )
        date_range = st.date_input(
            "Filter by Publication Date Range",
            [],
            key="date_filter",
            on_change=reset_page  # Reset page when this filter changes
        )

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

    # Query laws with loading animation
    with st.spinner("Loading Judgments..."):
        laws = query_laws(client, filters, skip, page_size)
        total_laws = count_laws(client, filters)

    if laws:
        st.markdown(f"### Page {page} (Showing {len(laws)} of {total_laws} laws)")
        for law in laws:
            with st.container():
                # Render law card
                st.markdown(f"""
                    <div class="law-card">
                        <div class="law-title">{law['Name']} (ID: {law['CaseNumber']})</div>
                        <div class="law-meta">Publication Date: {law.get('DecisionDate', 'N/A')}</div>
                        <div class="law-meta">Procedure Type: {law.get('ProcedureType', 'N/A')}</div>
                    </div>
                """, unsafe_allow_html=True)

                # Align buttons in a horizontal layout
                col1, col2 = st.columns([1, 1])

                with col1:
                    # View full details button
                    if st.button(f"View Full Details for {law['CaseNumber']}", key=f"details_{law['CaseNumber']}"):
                        with st.spinner("Loading full details..."):
                            full_law = load_full_law_details(client, law['CaseNumber'])
                            if full_law:
                                st.json(full_law)  # Show full law details as JSON
                            else:
                                st.error(f"Unable to load full details for CaseNumber {law['CaseNumber']}")

                with col2:
                    # File download button
                    documents = law.get('Documents', [])  # Get the Documents array
                    if documents and isinstance(documents, list) and 'url' in documents[
                        0]:  # Check if the first document has a 'url'
                        document_url = documents[0]['url']  # Extract the URL
                        file_content = download_file(document_url)
                        if file_content:
                            file_extension = document_url.split('.')[-1]
                            file_name = f"{law.get('CaseNumber', 'unknown')}.{file_extension}"  # Generate a file name based on CaseNumber
                            st.download_button(
                                label="Download Judgment",
                                data=file_content,
                                file_name=file_name,
                                mime="application/octet-stream"
                            )

        # Pagination controls
        total_pages = (total_laws + page_size - 1) // page_size
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

    client.close()


if __name__ == "__main__":
    main()
