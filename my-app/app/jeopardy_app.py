import streamlit as st
from neo4j import GraphDatabase
import fitz  # PyMuPDF
import tiktoken
from langchain_openai import OpenAI
from langchain_core.prompts import PromptTemplate

# Neo4j configuration
uri = "bolt://localhost:7687"
user = "neo4j"
password = "admin123"

class Neo4jConnection:
    def __init__(self, uri, user, password):
        self._driver = GraphDatabase.driver(uri, auth=(user, password))

    def close(self):
        self._driver.close()

    def fetch_questions(self):
        query = "MATCH (q:Question) RETURN q.text AS question"
        with self._driver.session() as session:
            result = session.run(query)
            questions = [record["question"] for record in result]
        return questions

def extract_text_from_pdf(pdf_path):
    document = fitz.open(pdf_path)
    text = ''
    for page_num in range(len(document)):
        page = document.load_page(page_num)
        text += page.get_text()
    return text

def get_pdf_text_truncated(pdf_path):
    pdf_text = extract_text_from_pdf(pdf_path)
    tokenizer = tiktoken.get_encoding("cl100k_base")
    max_context_length = 3800 - 256
    pdf_tokens = tokenizer.encode(pdf_text)
    if len(pdf_tokens) > max_context_length:
        pdf_tokens = pdf_tokens[:max_context_length]
    return tokenizer.decode(pdf_tokens)

def answer_question(question, context):
    openai_api_key = "your_openai_api_key"
    llm = OpenAI(api_key=openai_api_key)
    prompt_template = PromptTemplate(
        template="Answer the following question based on the given context:\n\nContext: {context}\n\nQuestion: {question}\nAnswer:",
        input_variables=["context", "question"]
    )
    prompt = prompt_template.format(context=context, question=question)
    response = llm.invoke(prompt)
    return response.strip()

# Streamlit App
st.title("Jeopardy Game")

# Connect to Neo4j and fetch questions
conn = Neo4jConnection(uri, user, password)
questions = conn.fetch_questions()
conn.close()

pdf_path = 'menu.pdf'
pdf_text = get_pdf_text_truncated(pdf_path)

categories = {"General Knowledge": questions}

selected_category = st.selectbox("Select a Category", list(categories.keys()))

if selected_category:
    st.header(f"Category: {selected_category}")
    for question in categories[selected_category]:
        if st.button(question):
            st.write(f"**Question:** {question}")
            answer = answer_question(question, pdf_text)
            st.write(f"**Answer:** {answer}")

# Footer
st.write("Select a category and click on the question to see the question. The answer will be displayed automatically.")
