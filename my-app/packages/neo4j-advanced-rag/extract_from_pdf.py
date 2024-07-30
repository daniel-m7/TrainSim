import fitz  # PyMuPDF

def extract_text_from_pdf(pdf_path):
    document = fitz.open(pdf_path)
    text = ''
    for page_num in range(len(document)):
        page = document.load_page(page_num)
        text += page.get_text()
    return text

def write_text_to_file(text, output_path):
    with open(output_path, 'w', encoding='utf-8') as file:
        file.write(text)

pdf_path = 'menu.pdf'
output_path = 'extracted_text.txt'

# Extract text from the PDF
text = extract_text_from_pdf(pdf_path)

# Write the extracted text to a file
write_text_to_file(text, output_path)

