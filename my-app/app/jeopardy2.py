import streamlit as st
import pandas as pd
from langchain_community.graphs import Neo4jGraph

# Initialize Neo4jGraph using default configuration
graph = Neo4jGraph()

# Fetch data from Neo4j
def fetch_jeopardy_data():
    query = """
    MATCH (cat:CategorySection)<-[:IN_CATEGORY]-(q:Question)-[:HAS_ANSWER]-(a:Answer)
    RETURN cat.title AS category, q.text AS question, q.points AS points, a.text AS answer
    ORDER BY category, points
    """
    result = graph.query(query)
    data = [{
        "category": record["category"],
        "question": record["question"],
        "points": record["points"],
        "answer": record["answer"]
    } for record in result]
    return pd.DataFrame(data)

# Load data and handle duplicates by aggregating questions with the same category and points
df = fetch_jeopardy_data()

# Combine questions with the same category and points by joining them with a separator
questions_aggregated_df = df.groupby(['category', 'points']).agg({
    'question': ' | '.join,
    'answer': ' | '.join
}).reset_index()

# Pivot and transpose the DataFrame to create a category-question matrix
transposed_df = questions_aggregated_df.pivot(index="points", columns="category", values="question")

# Initialize session state for clicked questions and score
if 'clicked_questions' not in st.session_state:
    st.session_state.clicked_questions = set()
if 'score' not in st.session_state:
    st.session_state.score = 0
if 'current_question' not in st.session_state:
    st.session_state.current_question = None
if 'current_answer' not in st.session_state:
    st.session_state.current_answer = None
if 'current_points' not in st.session_state:
    st.session_state.current_points = None

# Title of the app (centered)
st.markdown("<h1 style='text-align: center;'>Jeopardy Game</h1>", unsafe_allow_html=True)

# Define unique categories and points
categories = transposed_df.columns
points_levels = transposed_df.index

# Layout: Categories on the left, Question panel on the right
col1, col2 = st.columns([3, 1])

with col1:
    # Display category headers
    category_columns_layout = st.columns(len(categories))
    for i, category in enumerate(categories):
        with category_columns_layout[i]:
            st.markdown(f"<div style='text-align: center;'><strong>{category}</strong></div>", unsafe_allow_html=True)

    # Display questions based on the transposed DataFrame
    for point in points_levels:
        row_columns = st.columns(len(categories))
        for i, category in enumerate(categories):
            question = transposed_df.at[point, category]
            if pd.notna(question):  # Only display non-empty cells
                with row_columns[i]:
                    question_key = f"{category}-{point}"

                    # Check if the question is already clicked
                    if question_key not in st.session_state.clicked_questions:
                        # Button to reveal the question
                        if st.button(f"{point}", key=question_key, help=question):
                            st.session_state.clicked_questions.add(question_key)
                            st.session_state.current_question = question
                            st.session_state.current_points = point
                            st.session_state.current_answer = questions_aggregated_df[
                                (questions_aggregated_df['category'] == category) & 
                                (questions_aggregated_df['points'] == point)
                            ]['answer'].values[0]
                            st.rerun()
                    else:
                        st.write(f"Answered {point}")

with col2:
    # Score display on the right side
    st.markdown(f"<div style='text-align: right; font-size: large;'><strong>Your Score: {st.session_state.score}</strong></div>", unsafe_allow_html=True)

    # Display the question panel if a question is selected
    if st.session_state.current_question:
        st.markdown("<div style='background-color: #ADD8E6; padding: 10px;'><strong>Question:</strong></div>", unsafe_allow_html=True)
        st.write(st.session_state.current_question)

        # Answer input and check
        answer = st.text_input("Your Answer", key="current_answer_input")
        if st.button("Submit Answer"):
            correct_answer = st.session_state.current_answer.lower()
            if answer.lower() == correct_answer:
                st.success("Correct!")
                st.session_state.score += st.session_state.current_points
            else:
                st.error(f"Incorrect! The correct answer was: {correct_answer}")
            st.session_state.current_question = None
            st.session_state.current_answer = None
            st.session_state.current_points = None
            st.rerun()

# Close Neo4j connection after the game
if st.button("End Game"):
    graph.close()
