from neo4j_advanced_rag.chain import chain
from neo4j import GraphDatabase
from langchain_core.prompts import PromptTemplate
from langchain_openai import OpenAI
import fitz  # PyMuPDF
import tiktoken  # Import tiktoken for token counting




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

# Replace these variables with your actual Neo4j credentials and server details
uri = "bolt://localhost:7687"
user = "neo4j"
password = "admin123"

# Fetch questions from Neo4j
conn = Neo4jConnection(uri, user, password)
questions = conn.fetch_questions()
conn.close()

# Load the PDF text
pdf_path = 'menu.pdf'
def extract_text_from_pdf(pdf_path):
    document = fitz.open(pdf_path)
    text = ''
    for page_num in range(len(document)):
        page = document.load_page(page_num)
        text += page.get_text()
    return text

pdf_text = extract_text_from_pdf(pdf_path)

# Truncate PDF text to fit within token limits using tiktoken
tokenizer = tiktoken.get_encoding("cl100k_base")  # Use the appropriate encoding for your model
max_context_length = 3800 - 256  # Assuming we reserve 256 tokens for the completion

pdf_tokens = tokenizer.encode(pdf_text)
if len(pdf_tokens) > max_context_length:
    pdf_tokens = pdf_tokens[:max_context_length]

pdf_text = tokenizer.decode(pdf_tokens)

# Initialize LangChain LLM with the loaded PDF text
openai_api_key = "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"
llm = OpenAI(api_key=openai_api_key)

def answer_question(question, context):
    prompt_template = PromptTemplate(
        template="Answer the following question based on the given context:\n\nContext: {context}\n\nQuestion: {question}\nAnswer:",
        input_variables=["context", "question"]
    )
    prompt = prompt_template.format(context=context, question=question)
    response = llm.invoke(prompt)
    return response.strip()

# Dictionary to store questions and answers
qa_dict = {}

# Loop through questions, get answers, and store in dictionary
for question in questions:
    answer = answer_question(question, pdf_text)  # Pass the context (pdf_text) correctly here
    qa_dict[question] = answer

# Print the dictionary with questions and answers
print(qa_dict)