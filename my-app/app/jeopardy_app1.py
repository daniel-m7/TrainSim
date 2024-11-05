import streamlit as st
import pandas as pd
from neo4j import GraphDatabase
import textdistance  # Import textdistance

# Neo4j configuration
uri = "bolt://localhost:7687"
username = "neo4j"
password = "admin123"

# Neo4j connection setup
driver = GraphDatabase.driver(uri, auth=(username, password))

class Neo4jConnection:
    def __init__(self, uri, user, pwd):
        self._driver = GraphDatabase.driver(uri, auth=(user, pwd))

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

# Initialize session state
if 'clicked_questions' not in st.session_state:
    st.session_state.clicked_questions = set()

if 'score' not in st.session_state:
    st.session_state.score = 0

# Define callback functions
def reveal_question(question_key):
    st.session_state.clicked_questions.add(question_key)

def submit_answer(question_key, point, user_answer, correct_answer):
    # Calculate similarity percentage
    similarity = textdistance.jaro_winkler.normalized_similarity(user_answer.strip().lower(), correct_answer.strip().lower())
    similarity_percentage = round(similarity * 100, 2)

    # Calculate partial points based on similarity percentage
    partial_points = int(point * (similarity_percentage / 100))

    # Store similarity percentage in session state
    st.session_state[f"{question_key}_similarity"] = similarity_percentage

    # Award points based on similarity
    if user_answer.strip().lower() == correct_answer.strip().lower():
        st.session_state[f"{question_key}_correct"] = True
        st.session_state.score += point  # Full points for an exact match
    else:
        st.session_state[f"{question_key}_correct"] = False
        st.session_state.score += partial_points  # Partial points for a close answer

    st.session_state[f"{question_key}_answered"] = True

# Title and score display
st.title("Jeopardy Game")
st.header(f"Your Score: {st.session_state.score}")

# Connect to Neo4j and retrieve data
conn = Neo4jConnection(uri=uri, user=username, pwd=password)
query = '''
MATCH (a:Answer)<-[:HAS_ANSWER]-(q:Question)-[:IN_CATEGORY]->(c:CategorySection)
RETURN c.title as category, q.text AS question, q.points AS points, a.text as answer
ORDER BY c.title, q.points  
'''
data = conn.run_query(query)
conn.close()

# Convert the result to a DataFrame
df = get_dataframe_from_query(data)

if df.empty:
    st.write("No data available. Please check the Neo4j database or ingestion process.")
else:
    # Display categories as columns
    categories = df['category'].unique()
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

                    if question_key not in st.session_state.clicked_questions:
                        st.button(f"{point}", key=question_key, on_click=reveal_question, args=(question_key,))
                    else:
                        st.write(f"**Question:** {question}")
                        user_answer = st.text_input("Your answer:", key=f"answer_input_{question_key}")

                        if st.button("Submit", key=f"submit_{question_key}",
                                     on_click=submit_answer, args=(question_key, point, user_answer, answer)):
                            pass

                        if st.session_state.get(f"{question_key}_answered", False):
                            if st.session_state.get(f"{question_key}_correct", False):
                                st.success("Correct!")
                            else:
                                st.error(f"Incorrect! The correct answer was: {answer}")

                            # Display similarity percentage
                            similarity_percentage = st.session_state.get(f"{question_key}_similarity", 0)
                            st.write(f"Similarity: {similarity_percentage}%")

# Reset score button
if st.button("Reset Score"):
    st.session_state.score = 0
