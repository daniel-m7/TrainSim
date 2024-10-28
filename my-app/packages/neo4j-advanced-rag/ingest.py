from pathlib import Path
from typing import List

from langchain_community.document_loaders import TextLoader
from langchain_community.graphs import Neo4jGraph
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.pydantic_v1 import BaseModel, Field
from langchain_openai import ChatOpenAI, OpenAIEmbeddings
from langchain_text_splitters import TokenTextSplitter
from neo4j.exceptions import ClientError

txt_path = Path(__file__).parent / "extracted_text.txt"

graph = Neo4jGraph()

# Embeddings & LLM models
embeddings = OpenAIEmbeddings()
embedding_dimension = 1536
llm = ChatOpenAI(temperature=0)

# Load the text file
loader = TextLoader(str(txt_path), encoding="utf-8")
documents = loader.load()

# Ingest Parent-Child node pairs
parent_splitter = TokenTextSplitter(chunk_size=512, chunk_overlap=24)
child_splitter = TokenTextSplitter(chunk_size=100, chunk_overlap=24)
parent_documents = parent_splitter.split_documents(documents)

class JeopardyQuestion(BaseModel):
    """Structuring questions with categories, points, and answers."""
    category: str = Field(..., description="Jeopardy-style category")
    question: str = Field(..., description="Generated question")
    answer: str = Field(..., description="Generated answer")
    points: int = Field(..., description="Point value associated with the question")

class JeopardyQuestions(BaseModel):
    """Generating hypothetical Jeopardy-style questions with answers."""
    categories: List[str] = Field(..., description="List of generated categories")
    questions: List[JeopardyQuestion] = Field(
        ..., description="List of questions with their categories, answers, and points"
    )

questions_prompt = ChatPromptTemplate.from_messages(
    [
        (
            "system",
            (
                "You are generating hypothetical Jeopardy-style questions, answers, and six distinct categories "
                "based on the information found in the text. Ensure that each category has at least 5 questions, "
                "with point values increasing from 100 to 500 as the questions get more difficult. For each question, "
                "also generate the correct answer."
            ),
        ),
        (
            "human",
            (
                "Use the given format to generate hypothetical questions, answers, and Jeopardy-style categories from the "
                "following input: {input}"
            ),
        ),
    ]
)

question_chain = questions_prompt | llm.with_structured_output(JeopardyQuestions)

for i, parent in enumerate(parent_documents):
    jeopardy_data = question_chain.invoke(parent.page_content)
    categories = jeopardy_data.categories
    questions = jeopardy_data.questions

    # Ensure only 6 categories are used, each with at least 5 questions
    category_question_count = {}
    for question_data in questions:
        category = question_data.category
        if category not in category_question_count:
            category_question_count[category] = []
        category_question_count[category].append(question_data)

    selected_categories = [cat for cat, qs in category_question_count.items() if len(qs) >= 5]
    if len(selected_categories) > 6:
        selected_categories = selected_categories[:6]

    # Ingest the selected categories, questions, and answers
    for category in selected_categories:
        questions_in_category = category_question_count[category]
        if len(questions_in_category) < 5:
            continue  # Skip categories with fewer than 5 questions

        params = {
            "parent_id": i,
            "category": category,
            "questions": [
                {
                    "text": q.question,
                    "id": f"{i}-{q.points}",
                    "points": q.points,
                    "embedding": embeddings.embed_query(q.question),
                    "answer": q.answer
                }
                for q in questions_in_category[:5]  # Ensure exactly 5 questions
            ],
        }
        graph.query(
            """
        MERGE (p:Parent {id: $parent_id})
        WITH p
        MERGE (cat:Category {name: $category})
        WITH p, cat
        UNWIND $questions AS question
        CREATE (q:Question {id: question.id})
        SET q.text = question.text, q.points = question.points
        MERGE (q)-[:IN_CATEGORY]->(cat)-[:FOR_PARENT]->(p)
        CREATE (a:Answer {text: question.answer})
        MERGE (q)-[:HAS_ANSWER]->(a)
        WITH q, question
        CALL db.create.setVectorProperty(q, 'embedding', question.embedding)
        YIELD node
        RETURN count(*)
        """,
            params,
        )
        # Create vector index
        try:
            graph.query(
                "CALL db.index.vector.createNodeIndex('hypothetical_questions', "
                "'Question', 'embedding', $dimension, 'cosine')",
                {"dimension": embedding_dimension},
            )
        except ClientError:  # already exists
            pass

# Ingest summaries (optional, left unchanged)

summary_prompt = ChatPromptTemplate.from_messages(
    [
        (
            "system",
            (
                "You are generating concise and accurate summaries based on the "
                "information found in the text."
            ),
        ),
        (
            "human",
            ("Generate a summary of the following input: {question}\n" "Summary:"),
        ),
    ]
)

summary_chain = summary_prompt | llm

for i, parent in enumerate(parent_documents):
    summary = summary_chain.invoke({"question": parent.page_content}).content
    params = {
        "parent_id": i,
        "summary": summary,
        "embedding": embeddings.embed_query(summary),
    }
    graph.query(
        """
    MERGE (p:Parent {id: $parent_id})
    MERGE (p)-[:HAS_SUMMARY]->(s:Summary)
    SET s.text = $summary
    WITH s
    CALL db.create.setVectorProperty(s, 'embedding', $embedding)
    YIELD node
    RETURN count(*)
    """,
        params,
    )
    # Create vector index
    try:
        graph.query(
            "CALL db.index.vector.createNodeIndex('summary', "
            "'Summary', 'embedding', $dimension, 'cosine')",
            {"dimension": embedding_dimension},
        )
    except ClientError:  # already exists
        pass
