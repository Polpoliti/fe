import streamlit as st
import pymongo
import requests
from io import BytesIO
from dotenv import load_dotenv
import os
from urllib.parse import urlparse

# Load environment variables
load_dotenv()

# Get database connection details
MONGO_URI = os.getenv('MONGO_URI')
DATABASE_NAME = os.getenv('DATABASE_NAME')

MIME_TYPES = {
    '.pdf': 'application/pdf',
    '.doc': 'application/msword',
    '.docx': 'application/vnd.openxmlformats-officedocument.wordprocessingml.document'
}

st.set_page_config(page_title="Mini Lawyer - Judgments", page_icon="⚖️", layout="wide")


# Reuse the same custom CSS from main.py

def init_connection():
    try:
        return pymongo.MongoClient(MONGO_URI)
    except Exception as e:
        st.error(f"Failed to connect to MongoDB: {str(e)}")
        return None


def get_file_extension_and_mime(url):
    path = urlparse(url).path.lower()
    for ext, mime_type in MIME_TYPES.items():
        if path.endswith(ext):
            return ext, mime_type
    return '.pdf', 'application/pdf'


def download_file(url):
    try:
        response = requests.get(url)
        if response.status_code == 200:
            return BytesIO(response.content)
        else:
            st.error(f"Failed to download file: HTTP {response.status_code}")
            return None
    except Exception as e:
        st.error(f"Error downloading file: {str(e)}")
        return None


def main():
    # Header (similar to main page)
    st.markdown("""
        <div class="header">
            <h1>🔍 Mini Lawyer - חיפוש פסקי דין</h1>
            <div class="nav-links">
                <a href="/" class="nav-link">חיפוש חוקים</a>
                <a href="/Judgments" class="nav-link">חיפוש פסקי דין</a>
            </div>
        </div>
    """, unsafe_allow_html=True)

    client = init_connection()
    if not client:
        return

    case_number = st.text_input("מספר תיק", placeholder="לדוגמה: 69349-12-20")

    if st.button("חפש"):
        if case_number:
            db = client[DATABASE_NAME]
            collection = db["judgments"]

            result = collection.find_one({"CaseNumber": str(case_number)})

            if result:
                st.success(f"נמצא תיק מספר: {result['CaseNumber']}")

                if 'Documents' in result and result['Documents']:
                    for i, doc in enumerate(result['Documents']):
                        if 'url' in doc:
                            st.markdown(f"**מסמך {i + 1}**")

                            file_ext, mime_type = get_file_extension_and_mime(doc['url'])

                            file_data = download_file(doc['url'])
                            if file_data:
                                st.download_button(
                                    label=f"הורד מסמך ({file_ext[1:].upper()})",
                                    data=file_data,
                                    file_name=f"case_{case_number}_doc_{i + 1}{file_ext}",
                                    mime=mime_type
                                )

                            st.markdown(f"קישור: {doc['url']}")
                else:
                    st.warning("לא נמצאו מסמכים עבור תיק זה")
            else:
                st.warning("תיק לא נמצא")

        else:
            st.error("אנא הכנס מספר תיק")

    client.close()


if __name__ == "__main__":
    main()