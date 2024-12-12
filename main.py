import streamlit as st
from dotenv import load_dotenv
import os

# Load environment variables
load_dotenv()

st.set_page_config(page_title="Mini Lawyer", page_icon="⚖️", layout="wide")


def main():
    st.title("⚖️ Mini Lawyer")

    st.markdown("""
        <div class="main-links">
            <h3>Explore our tools:</h3>
            <ul>
                <li><a href="/Judgments">🔍 Judgments Searching</a></li>
                <li><a href="/Laws">📜 Laws Searching</a></li>
            </ul>
        </div>
    """, unsafe_allow_html=True)


if __name__ == "__main__":
    main()
