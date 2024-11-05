import streamlit as st
import pandas as pd
from langchain_community.graphs import Neo4jGraph
import textdistance  # Import textdistance for similarity calculations

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

# Load data and handle duplicates
df = fetch_jeopardy_data()
questions_aggregated_df = df.groupby(['category', 'points']).agg({
    'question': ' | '.join,
    'answer': ' | '.join
}).reset_index()
transposed_df = questions_aggregated_df.pivot(index="points", columns="category", values="question")

# Initialize session state
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
if 'feedback' not in st.session_state:
    st.session_state.feedback = None

# Title of the app
st.markdown("<h1 style='text-align: center;'>Jeopardy Game</h1>", unsafe_allow_html=True)

# Define categories and points
categories = transposed_df.columns
points_levels = transposed_df.index

# Layout setup
col1, col2 = st.columns([3, 1])

with col1:
    category_columns_layout = st.columns(len(categories))
    for i, category in enumerate(categories):
        with category_columns_layout[i]:
            st.markdown(f"<div style='text-align: center;'><strong>{category}</strong></div>", unsafe_allow_html=True)

    for point in points_levels:
        row_columns = st.columns(len(categories))
        for i, category in enumerate(categories):
            question = transposed_df.at[point, category]
            if pd.notna(question):
                with row_columns[i]:
                    question_key = f"{category}-{point}"
                    if question_key not in st.session_state.clicked_questions:
                        if st.button(f"{point}", key=question_key, help=question):
                            st.session_state.clicked_questions.add(question_key)
                            st.session_state.current_question = question
                            st.session_state.current_points = point
                            st.session_state.current_answer = questions_aggregated_df[
                                (questions_aggregated_df['category'] == category) & 
                                (questions_aggregated_df['points'] == point)
                            ]['answer'].values[0]
                            st.session_state.feedback = None
                            st.rerun()
                    else:
                        st.write(f"Answered {point}")

with col2:
    st.markdown(f"<div style='text-align: right; font-size: large;'><strong>Your Score: {st.session_state.score}</strong></div>", unsafe_allow_html=True)

    if st.session_state.current_question:
        st.markdown("<div style='background-color: #ADD8E6; padding: 10px;'><strong>Question:</strong></div>", unsafe_allow_html=True)
        st.write(st.session_state.current_question)

        answer = st.text_input("Your Answer", key="current_answer_input")
        if st.button("Submit Answer"):
            correct_answer = st.session_state.current_answer.lower()
            similarity = textdistance.jaro_winkler.normalized_similarity(answer.lower(), correct_answer)
            similarity_percentage = round(similarity * 100, 2)
            partial_points = int(st.session_state.current_points * (similarity_percentage / 100))

            if answer.lower() == correct_answer:
                st.success("Correct!")
                st.session_state.score += st.session_state.current_points
                st.session_state.feedback = f"Correct! You earned {st.session_state.current_points} points."
            else:
                st.error(f"Incorrect! The correct answer was: {correct_answer}")
                st.session_state.score += partial_points
                st.session_state.feedback = (
                    f"Incorrect! The correct answer was: {correct_answer}. "
                    f"Your answer was {similarity_percentage}% correct. You earned {partial_points} points."
                )

            st.session_state.current_question = None
            st.session_state.current_answer = None
            st.session_state.current_points = None
            st.rerun()

    # Display feedback after the question panel disappears
    if st.session_state.feedback:
        st.write(st.session_state.feedback)

# Close Neo4j connection after the game
if st.button("End Game"):
    graph.close()
