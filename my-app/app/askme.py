import streamlit as st
from langchain_community.graphs import Neo4jGraph
from wordcloud import WordCloud
import matplotlib.pyplot as plt
from gtts import gTTS
import time
import os
import pygame
import uuid  # For generating unique filenames

# Initialize pygame mixer
pygame.mixer.init()

# Set Streamlit page configuration
st.set_page_config(layout="wide")

# Custom CSS to reduce top margin and set maximum width
st.markdown(
    """
    <style>
        .main .block-container {
            max-width: 85%;
            margin: auto;
            padding-top: 1rem; /* Reduce top padding */
        }
    </style>
    """,
    unsafe_allow_html=True
)

# Set up the Neo4j graph connection
graph = Neo4jGraph()

# Function to play text-to-speech audio
def speak_text(text):
    filename = f"temp_audio_{uuid.uuid4()}.mp3"  # Generate a unique filename
    tts = gTTS(text=text, lang='en')
    tts.save(filename)
    pygame.mixer.music.load(filename)
    pygame.mixer.music.play()
    while pygame.mixer.music.get_busy():
        time.sleep(0.1)  # Wait until playback finishes
    pygame.mixer.music.stop()
    pygame.mixer.music.unload()  # Unload the file to release it
    os.remove(filename)  # Remove the file after playback

# Streamlit layout
st.title("Question and Answer App")

# Query to get ingredients sorted by pageRank in descending order
ingredients_query = """
MATCH (ing:Ingredient)
RETURN ing.text AS ingredient, ing.pageRank AS pageRank
ORDER BY ing.pageRank DESC
"""
ingredients_data = graph.query(ingredients_query)

# Create a list of formatted ingredients for the dropdown
ranked_ingredients = [f"{record['pageRank']:.2f} : {record['ingredient']}" for record in ingredients_data]

# Align the "Select Ingredient and Question" and "Questions Related to Selected Ingredient" headers at the same level
header_col1, header_col2 = st.columns([5, 3])

with header_col1:
    st.subheader("Select Ingredient and Question")
    selected_ingredient_ranked = st.selectbox("Ranked Ingredients", ranked_ingredients)

with header_col2:
    st.subheader("Questions Related to Selected Ingredient")

# Extract the selected ingredient text from the dropdown value
selected_ingredient = selected_ingredient_ranked.split(" : ")[1]

# Create a two-column layout below the headers for the word cloud and questions
col1, col2 = st.columns([5, 3])

# Left Column: Display WordCloud
with col1:
    st.subheader("Ingredients WordCloud")
    wordcloud = WordCloud(width=1000, height=500, background_color='white')
    wordcloud_dict = {record["ingredient"]: record["pageRank"] for record in ingredients_data}
    wordcloud.generate_from_frequencies(wordcloud_dict)

    # Display the word cloud
    fig, ax = plt.subplots(figsize=(10, 5))  # Set a larger figure size for better visibility
    ax.imshow(wordcloud, interpolation="bilinear")
    ax.axis("off")
    st.pyplot(fig)

# Right Column: Display questions as buttons and auto-click them
with col2:
    questions_query = """
    MATCH (q:Question)-[:HAS_ANSWER]->(a:Answer)
    WHERE q.text CONTAINS $ingredient 
    RETURN q.text AS question_text, a.text AS answer_text
    """
    questions_data = graph.query(questions_query, {"ingredient": selected_ingredient})

    # Auto-click each question and speak it with answer
    for question in questions_data[:5]:
        question_text = question["question_text"]
        answer_text = question["answer_text"]
        
        # Speak the question text
        st.write(f"Question: {question_text}")
        speak_text(question_text)
        
        # Wait for 2 seconds before speaking the answer
        time.sleep(2)
        
        # Speak the answer text
        st.write("Answer:", answer_text)
        speak_text(answer_text)
