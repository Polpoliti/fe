import streamlit as st
st.set_page_config(page_title="Mini Lawyer - Laws", page_icon="📜", layout="wide")


from app_resources import mongo_client
from dotenv import load_dotenv
import os
from datetime import datetime

# Load environment variables
load_dotenv()

# Database details
MONGO_URI = os.getenv('MONGO_URI')
DATABASE_NAME = os.getenv('DATABASE_NAME')
COLLECTION_NAME = "laws"


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



# Query laws with pagination and filtering
def query_laws(client, filters=None, skip=0, limit=10):
    try:
        db = client[DATABASE_NAME]
        collection = db[COLLECTION_NAME]
        pipeline = []

        # Apply filters
        if filters:
            pipeline.append({"$match": filters})

        # Sort by IsraelLawID (or other criteria)
        pipeline.append({"$sort": {"IsraelLawID": 1}})

        # Skip and limit for pagination
        pipeline.append({"$skip": skip})
        pipeline.append({"$limit": limit})

        # Exclude heavy fields (Segments)
        pipeline.append({"$project": {"Segments": 0}})

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

# Load full details for a single law (include Segments)
def load_full_law_details(client, law_id):
    try:
        db = client[DATABASE_NAME]
        collection = db[COLLECTION_NAME]
        law = collection.find_one({"IsraelLawID": law_id})
        return law
    except Exception as e:
        st.error(f"Error fetching full details for law ID {law_id}: {str(e)}")
        return None

# Function to reset page to 1
def reset_page():
    st.session_state["page"] = 1

def main():
    st.title("📜 Laws Searching")

    # Initialize pagination state
    if "page" not in st.session_state:
        st.session_state["page"] = 1

    # Filters section
    with st.expander("Filters"):
        israel_law_id = st.number_input(
            "Filter by IsraelLawID (Exact Match)",
            min_value=0,
            step=1,
            value=0,
            key="law_id_filter",
            on_change=reset_page
        )
        law_name = st.text_input(
            "Filter by Name (Regex)",
            key="law_name_filter",
            on_change=reset_page
        )
        date_range = st.date_input(
            "Filter by Publication Date Range",
            [],
            key="date_filter",
            on_change=reset_page
        )

    # Pagination state
    page = st.session_state["page"]
    page_size = 10
    skip = (page - 1) * page_size

    # Build filters based on input
    filters = {}
    if israel_law_id > 0:
        filters["IsraelLawID"] = israel_law_id
    if law_name:
        filters["Name"] = {"$regex": law_name, "$options": "i"}
    if len(date_range) == 2:
        start_date, end_date = date_range
        filters["PublicationDate"] = {
            "$gte": datetime.combine(start_date, datetime.min.time()),
            "$lte": datetime.combine(end_date, datetime.max.time())
        }

    client = mongo_client

    # Query laws with loading animation
    with st.spinner("Loading laws..."):
        laws = query_laws(client, filters, skip, page_size)
        total_laws = count_laws(client, filters)

    if laws:
        st.markdown(f"### Page {page} (Showing {len(laws)} of {total_laws} laws)")
        for law in laws:
            law_description = law.get("Description", "").strip() or "אין תיאור לחוק זה"
            with st.container():
                st.markdown(f"""
                    <div class="law-card">
                        <div class="law-title">{law['Name']} (ID: {law['IsraelLawID']})</div>
                        <div class="law-description">{law_description}</div>
                        <div class="law-meta">Publication Date: {law.get('PublicationDate', 'N/A')}</div>
                    </div>
                """, unsafe_allow_html=True)

                if st.button(f"View Full Details for {law['IsraelLawID']}", key=f"details_{law['IsraelLawID']}"):
                    with st.spinner("Loading full details..."):
                        full_law = load_full_law_details(client, law['IsraelLawID'])
                        if full_law:
                            st.json(full_law)
                        else:
                            st.error(f"Unable to load full details for law ID {law['IsraelLawID']}")

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
        st.warning("No laws found with the applied filters.")


if __name__ == "__main__":
    main()
