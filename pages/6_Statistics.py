import os
import streamlit as st
import pandas as pd
import altair as alt
from pymongo import MongoClient
from dotenv import load_dotenv
from datetime import datetime

# Set page config as the first Streamlit command.
st.set_page_config(page_title="Statistics Page", page_icon="📊", layout="wide")

# Disable parallelism in tokenizers to avoid warnings
os.environ["TOKENIZERS_PARALLELISM"] = "false"

# Load environment variables
load_dotenv()
MONGO_URI = os.getenv("MONGO_URI")
DATABASE_NAME = os.getenv("DATABASE_NAME")
LAWS_COLLECTION = "laws"
JUDGMENTS_COLLECTION = "judgments"


# --- Data Loading Functions ---
@st.cache_data(show_spinner=False)
def load_laws_data():
    client = MongoClient(MONGO_URI)
    db = client[DATABASE_NAME]
    docs = list(db[LAWS_COLLECTION].find(
        {}, {"PublicationDate": 1, "IsBasicLaw": 1, "IsFavoriteLaw": 1}
    ))
    client.close()
    df = pd.DataFrame(docs)
    if not df.empty:
        if "_id" in df.columns:
            df = df.drop(columns=["_id"])
        if "PublicationDate" in df.columns:
            df["PublicationDate"] = pd.to_datetime(df["PublicationDate"], errors="coerce")
    return df


@st.cache_data(show_spinner=False)
def load_judgments_data():
    client = MongoClient(MONGO_URI)
    db = client[DATABASE_NAME]
    docs = list(db[JUDGMENTS_COLLECTION].find(
        {}, {"DecisionDate": 1, "CourtType": 1, "ProcedureType": 1, "District": 1}
    ))
    client.close()
    df = pd.DataFrame(docs)
    if not df.empty:
        if "_id" in df.columns:
            df = df.drop(columns=["_id"])
        if "DecisionDate" in df.columns:
            df["DecisionDate"] = pd.to_datetime(df["DecisionDate"], errors="coerce")
    return df


# --- Load Data ---
st.title("Statistics Page")
st.info("Loading data...")

df_judgments = load_judgments_data()
df_laws = load_laws_data()

st.write("Data loaded.")

# --- Judgments Statistics Section (at the top) ---
st.header("Judgments Statistics")

if not df_judgments.empty:
    # Timeline for DecisionDate
    timeline_chart = alt.Chart(df_judgments).mark_bar().encode(
        x=alt.X("year(DecisionDate):O", title="Year"),
        y=alt.Y("count()", title="Number of Judgments")
    ).properties(title="Judgments Timeline (Decision Date)")
    st.altair_chart(timeline_chart, use_container_width=True)

    # Pie chart for CourtType
    if "CourtType" in df_judgments.columns:
        court_chart = alt.Chart(df_judgments).mark_arc().encode(
            theta=alt.Theta("count()", stack=True),
            color=alt.Color("CourtType:N", legend=alt.Legend(title="Court Type"))
        ).properties(title="Distribution of Court Type")
        st.altair_chart(court_chart, use_container_width=True)

    # Pie chart for ProcedureType
    if "ProcedureType" in df_judgments.columns:
        procedure_chart = alt.Chart(df_judgments).mark_arc().encode(
            theta=alt.Theta("count()", stack=True),
            color=alt.Color("ProcedureType:N", legend=alt.Legend(title="Procedure Type"))
        ).properties(title="Distribution of Procedure Type")
        st.altair_chart(procedure_chart, use_container_width=True)

    # Pie chart for District
    if "District" in df_judgments.columns:
        district_chart = alt.Chart(df_judgments).mark_arc().encode(
            theta=alt.Theta("count()", stack=True),
            color=alt.Color("District:N", legend=alt.Legend(title="District"))
        ).properties(title="Distribution of District")
        st.altair_chart(district_chart, use_container_width=True)
else:
    st.info("No judgments data available.")

# --- Laws Statistics Section ---
st.markdown("---")
st.header("Laws Statistics")

if not df_laws.empty:
    # Timeline for PublicationDate
    timeline_laws = alt.Chart(df_laws).mark_bar().encode(
        x=alt.X("year(PublicationDate):O", title="Year"),
        y=alt.Y("count()", title="Number of Laws")
    ).properties(title="Laws Timeline (Publication Date)")
    st.altair_chart(timeline_laws, use_container_width=True)

    # Bar chart for IsBasicLaw
    if "IsBasicLaw" in df_laws.columns:
        basic_chart = alt.Chart(df_laws).mark_bar().encode(
            x=alt.X("IsBasicLaw:N", title="Is Basic Law (True/False)"),
            y=alt.Y("count()", title="Count")
        ).properties(title="Distribution of IsBasicLaw")
        st.altair_chart(basic_chart, use_container_width=True)

    # Bar chart for IsFavoriteLaw
    if "IsFavoriteLaw" in df_laws.columns:
        favorite_chart = alt.Chart(df_laws).mark_bar().encode(
            x=alt.X("IsFavoriteLaw:N", title="Is Favorite Law (True/False)"),
            y=alt.Y("count()", title="Count")
        ).properties(title="Distribution of IsFavoriteLaw")
        st.altair_chart(favorite_chart, use_container_width=True)
else:
    st.info("No laws data available.")

st.info("Statistics page loaded successfully.")
