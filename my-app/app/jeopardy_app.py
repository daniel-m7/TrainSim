import streamlit as st
import pandas as pd
from neo4j import GraphDatabase
import random

# Neo4j configuration
uri = "bolt://localhost:7687"
user = "neo4j"
password = "admin123"

class Neo4jConnection:
    def __init__(self, uri, user, password):
        self._driver = GraphDatabase.driver(uri, auth=(user, password))

    def close(self):
        self._driver.close()

    def run_query(self, query):
        with self._driver.session() as session:
            result = session.run(query)
            data = [dict(record) for record in result]
        return data

def get_dataframe_from_query(data):
    df = pd.DataFrame(data)
    if not df.empty:
        df.columns = ['category', 'question', 'points']
    return df

def display_question(category, question, points):
    st.write(f"**Question for {points} points in {category}:** {question}")
    if st.button("Show Answer", key=f"show_answer_{category}_{points}"):
        st.write(f"**Answer:** [Display the answer here]")  # Replace with actual logic if needed
        st.session_state.score += points

# Streamlit App
st.title("Server Training Jeopardy Game")

# Initialize session state
if "score" not in st.session_state:
    st.session_state.score = 0

conn = Neo4jConnection(uri, user, password)

# Run the Cypher query to retrieve all categories, questions, and points
query = """
MATCH (q:Question)-[:IN_CATEGORY]->(c:Category)
RETURN c.name as category, q.text AS question, q.points AS points ORDER BY c.name
"""
data = conn.run_query(query)

# Convert the result to a DataFrame
df = get_dataframe_from_query(data)

# Check if the DataFrame is empty before proceeding
if df.empty:
    st.write("No data available. Please check the Neo4j database or ingestion process.")
else:
    # Filter to select only categories with at least 5 questions
    category_counts = df['category'].value_counts()
    selected_categories = category_counts[category_counts >= 5].index.tolist()

    # Select 4 random categories
    if len(selected_categories) > 4:
        selected_categories = random.sample(selected_categories, 4)

    # Filter the DataFrame to include only the selected categories and first 5 questions per category
    filtered_df = df[df['category'].isin(selected_categories)]
    filtered_df = filtered_df.groupby('category').head(5)

    # Display the Jeopardy board
    st.subheader("Select a category and click on the point value to see the question. Click 'Show Answer' to reveal the answer.")
    cols = st.columns(len(selected_categories))

    for idx, category in enumerate(selected_categories):
        with cols[idx]:
            st.header(category)
            category_df = filtered_df[filtered_df['category'] == category]
            for _, row in category_df.iterrows():
                points = row["points"]
                question = row["question"]
                if st.button(f"{points}", key=f"{category}_{points}"):
                    st.session_state["current_question"] = (category, question, points)
                    st.session_state["question_displayed"] = True
                    st.rerun()  # Updated to use the new rerun method

    # Display the current question and answer if a point button is clicked
    if st.session_state.get("question_displayed"):
        category, question, points = st.session_state["current_question"]
        display_question(category, question, points)
        st.session_state["question_displayed"] = False  # Reset to ensure the question isn't displayed again automatically

    # Show the current score
    st.write(f"**Score:** {st.session_state.score}")

# Footer
st.write("Select a category and click on the point value to see the question. Click 'Show Answer' to reveal the answer.")

conn.close()
