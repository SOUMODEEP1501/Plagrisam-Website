import os
import nltk
import logging
from nltk.tokenize import word_tokenize
from nltk.corpus import stopwords
from itertools import combinations

# Ensure necessary NLTK data is available
nltk.download("punkt")
nltk.download("stopwords")

# Configure logging
logging.basicConfig(level=logging.INFO, format="%(levelname)s - %(message)s")

# Threshold for plagiarism detection (Adjustable)
PLAGIARISM_THRESHOLD = 50  # 50% similarity = plagiarized

def preprocess_text(text):
    """Tokenizes text and removes stopwords."""
    try:
        tokens = word_tokenize(text.lower())  # Convert to lowercase and tokenize
        tokens = [word for word in tokens if word.isalnum()]  # Remove punctuation
        stop_words = set(stopwords.words("english"))
        filtered_tokens = [word for word in tokens if word not in stop_words]
        return filtered_tokens
    except Exception as e:
        logging.error(f"Error in text preprocessing: {e}")
        return []

def read_documents(folder_path):
    """Reads all valid .txt documents in the folder, excluding empty files."""
    documents = []
    filenames = []
    
    for file_name in os.listdir(folder_path):
        if not file_name.endswith(".txt"):
            continue  # Skip non-text files
        
        file_path = os.path.join(folder_path, file_name)
        
        try:
            with open(file_path, "r", encoding="utf-8") as file:
                content = file.read().strip()
                
                if content:  # Ensure file is not empty
                    documents.append(content)
                    filenames.append(file_name)
                else:
                    logging.warning(f"⚠️ Skipping {file_name}: No meaningful content after preprocessing.")
        
        except Exception as e:
            logging.error(f"❌ Error reading {file_name}: {e}")

    return documents, filenames

def calculate_similarity(doc1, doc2):
    """Computes Jaccard similarity between two tokenized documents."""
    set1, set2 = set(doc1), set(doc2)
    intersection = len(set1 & set2)
    union = len(set1 | set2)
    similarity = (intersection / union) * 100 if union != 0 else 0
    return round(similarity, 2)

def check_plagiarism(folder_path):
    """Main function to check plagiarism among text documents."""
    documents, filenames = read_documents(folder_path)

    if len(documents) < 2:
        logging.error("❌ Not enough valid documents to perform plagiarism detection.")
        return

    logging.info("🔍 Checking for plagiarism...")

    processed_docs = [preprocess_text(doc) for doc in documents]
    plagiarism_results = []

    for (i, doc1), (j, doc2) in combinations(enumerate(processed_docs), 2):
        similarity = calculate_similarity(doc1, doc2)
        result = f"{filenames[i]} ↔ {filenames[j]}: {similarity}% similarity"
        
        if similarity >= PLAGIARISM_THRESHOLD:
            result += " 🚨 PLAGIARIZED!"
        else:
            result += " ✅ No plagiarism."
        
        plagiarism_results.append(result)

    if plagiarism_results:
        print("\n📊 Plagiarism Report:")
        for res in plagiarism_results:
            print(res)
    else:
        print("✅ No plagiarism detected.")

if __name__ == "__main__":
    # Set the correct folder path
    folder_path = r"C:\Users\ADMIN\Desktop\plagiarism detector in python\documents"
    check_plagiarism(folder_path)
