import os
import re
from dotenv import load_dotenv
from langchain_community.document_loaders import PyPDFLoader
from langchain_openai import OpenAIEmbeddings
from langchain_community.vectorstores import Chroma
from langchain_core.documents import Document
from langchain_text_splitters import RecursiveCharacterTextSplitter

# ==========================================
# ΑΣΦΑΛΗΣ ΦΟΡΤΩΣΗ API KEY
# ==========================================
load_dotenv(override=True)
current_key = os.environ.get("OPENAI_API_KEY", "")

if not current_key:
    print("❌ Σφάλμα: Δεν βρέθηκε OPENAI_API_KEY στο αρχείο .env!")
    exit(1)

print(f"🔑 Using API Key ending in: ...{current_key[-4:]}")

# ==========================================
# ΡΥΘΜΙΣΕΙΣ ΑΡΧΕΙΩΝ & ΒΑΣΗΣ
# ==========================================
PDF_PATH = "eu_ai_act.pdf" # Το αρχείο που μόλις κατεβάσαμε
CHROMA_DB_DIR = "./chroma_db"

def perform_legal_chunking(pages):
    print("\n✂️ Ξεκινάει ο τεμαχισμός με Recursive Splitting...")
    full_text = "\n".join([page.page_content for page in pages])
    
    # Το επαγγελματικό εργαλείο τεμαχισμού
    text_splitter = RecursiveCharacterTextSplitter(
        chunk_size=3000,      # Ιδανικό μέγεθος για ακρίβεια RAG
        chunk_overlap=300,    # Επικάλυψη για να μη χάνεται το νόημα στις αλλαγές σελίδας
        length_function=len,
        separators=["\nArticle", "\nAnnex", "\n\n", "\n", " ", ""]
    )
    
    # Χωρίζουμε το κείμενο
    raw_chunks = text_splitter.split_text(full_text)
    
    documents = []
    for i, chunk in enumerate(raw_chunks):
        if len(chunk.strip()) < 50:
            continue
            
        metadata = {
            "source": "Regulation_EU_2024_1689",
            "chunk_id": str(i),
            "type": "law_text"
        }
        
        doc = Document(page_content=chunk.strip(), metadata=metadata)
        documents.append(doc)
        
    print(f"✅ Δημιουργήθηκαν {len(documents)} ισορροπημένα chunks.")
    return documents

def main():
    print(f"\n📄 Ανάγνωση αρχείου: {PDF_PATH}")
    if not os.path.exists(PDF_PATH):
        print(f"❌ Το αρχείο '{PDF_PATH}' δεν βρέθηκε. Βεβαιώσου ότι έτρεξες την εντολή wget.")
        return

    loader = PyPDFLoader(PDF_PATH)
    pages = loader.load()
    
    legal_chunks = perform_legal_chunking(pages)
    
    print("\n🧠 Δημιουργία Semantic Embeddings...")
    embeddings = OpenAIEmbeddings(model="text-embedding-3-small")
    
    print(f"💾 Αποθήκευση στο Local Vector Store ('{CHROMA_DB_DIR}'). Αυτό μπορεί να πάρει 1-2 λεπτά...")
    Chroma.from_documents(
        documents=legal_chunks, 
        embedding=embeddings, 
        persist_directory=CHROMA_DB_DIR
    )
    
    print("\n🎉 Το Offline Ingestion του πραγματικού νόμου ολοκληρώθηκε με απόλυτη επιτυχία!")

if __name__ == "__main__":
    main()