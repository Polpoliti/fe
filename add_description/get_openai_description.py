import openai
import time
from pymongo import MongoClient, UpdateOne

openai_client = openai.OpenAI(
    api_key="")
# MongoDB client
mongo_client = MongoClient("")
db = mongo_client["final_project"]
collection = db["laws"]


def trim_to_word_limit(text, limit=300):
    words = text.split()
    return " ".join(words[:limit]) if len(words) > limit else text


def summarize_law(law_name, content):
    prompt = f"""אנא סכם את המידע הבא על החוק ל-100 מילים בעברית.
החוק: {law_name}

המידע:
{content}

התשובה צריכה להיות תמציתית ומפורטת, לכלול את עיקרי החוק, מה החוק אומר, לאילו זכויות הוא מתייחס, ועל מי הוא בא להגן."""
    response = openai_client.chat.completions.create(
        model="gpt-3.5-turbo",
        messages=[{"role": "user", "content": prompt}],
        temperature=0.7
    )
    return response.choices[0].message.content.strip()


BATCH_SIZE = 5
docs = list(collection.find({"Description": {"$exists": False}}, {"Name": 1, "IsraelLawID": 1, "Segments": 1}))
total = len(docs)
print(f"Total documents to process: {total}")

for i in range(0, total, BATCH_SIZE):
    batch = docs[i:i + BATCH_SIZE]
    bulk_ops = []
    for doc in batch:
        law_name = doc.get("Name", "")
        segments = doc.get("Segments", [])
        combined_text = " ".join(seg.get("SectionContent", "") for seg in segments)
        trimmed_text = trim_to_word_limit(combined_text, limit=300)
        summary = summarize_law(law_name, trimmed_text)
        bulk_ops.append(
            UpdateOne({"IsraelLawID": doc["IsraelLawID"]}, {"$set": {"Description": summary}})
        )
        print(f"Updated law {doc['IsraelLawID']} with summary.")
        time.sleep(0.5)
    if bulk_ops:
        result = collection.bulk_write(bulk_ops)
        print(f"Processed {min(i + BATCH_SIZE, total)} / {total}")
    time.sleep(0.5)
