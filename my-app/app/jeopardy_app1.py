import streamlit as st
import pandas as pd
from neo4j import GraphDatabase

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
        df.columns = ['category', 'question', 'points', 'answer']
    return df

# Initialize session state to keep track of clicked questions, score, and responses
if 'clicked_questions' not in st.session_state:
    st.session_state.clicked_questions = set()

if 'score' not in st.session_state:
    st.session_state.score = 0

# Define callback functions for buttons
def reveal_question(question_key):
    st.session_state.clicked_questions.add(question_key)

def submit_answer(question_key, point, user_answer, correct_answer):
    if user_answer.strip().lower() == correct_answer.strip().lower():
        st.session_state[f"{question_key}_correct"] = True
        st.session_state.score += point
    else:
        st.session_state[f"{question_key}_correct"] = False
    st.session_state[f"{question_key}_answered"] = True

# Title of the app
st.title("Jeopardy Game")

# Display the current score only once at the top
st.header(f"Your Score: {st.session_state.score}")

# Connect to Neo4j and retrieve data
conn = Neo4jConnection(uri, user, password)
query = '''
MATCH (a:Answer)<-[:HAS_ANSWER]-(q:Question)-[:IN_CATEGORY]->(c:Category)
RETURN c.name as category, q.text AS question, q.points AS points, a.text as answer
ORDER BY c.name, q.points  
'''
data = conn.run_query(query)
conn.close()

# Convert the result to a DataFrame
df = get_dataframe_from_query(data)

# Ensure there is data to display
if df.empty:
    st.write("No data available. Please check the Neo4j database or ingestion process.")
else:
    # Define the unique categories
    categories = df['category'].unique()

    # Display categories as columns
    columns = st.columns(len(categories))
    for i, category in enumerate(categories):
        with columns[i]:
            st.write(f"### {category}")

    # Display the questions and points for each category
    for point in sorted(df['points'].unique()):
        columns = st.columns(len(categories))
        for i, category in enumerate(categories):
            with columns[i]:
                question_data = df[(df['category'] == category) & (df['points'] == point)]
                if not question_data.empty:
                    question = question_data['question'].values[0]
                    answer = question_data['answer'].values[0]
                    question_key = f"{category}_{point}"

                    # Check if question has been clicked; otherwise, show the point button
                    if question_key not in st.session_state.clicked_questions:
                        st.button(f"{point}", key=question_key, on_click=reveal_question, args=(question_key,))
                    else:
                        # Show the question once it has been clicked
                        st.write(f"**Question:** {question}")
                        user_answer = st.text_input("Your answer:", key=f"answer_input_{question_key}")

                        # Submit answer and check for correctness
                        if st.button("Submit", key=f"submit_{question_key}",
                                     on_click=submit_answer, args=(question_key, point, user_answer, answer)):
                            pass
                        
                        # Check if answer has been submitted for this question
                        if st.session_state.get(f"{question_key}_answered", False):
                            if st.session_state.get(f"{question_key}_correct", False):
                                st.success("Correct!")
                            else:
                                st.error(f"Incorrect! The correct answer was: {answer}")

# Reset score option at the end of the page
if st.button("Reset Score"):
    st.session_state.score = 0
