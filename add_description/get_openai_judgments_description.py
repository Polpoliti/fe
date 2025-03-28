import openai
import time
from pymongo import MongoClient, UpdateOne

openai_client = openai.OpenAI(
    api_key="")

mongo_client = MongoClient("")
db = mongo_client["final_project"]
collection = db["judgments"]


def trim_to_word_limit(text, limit=1000):
    words = text.split()
    return " ".join(words[:limit]) if len(words) > limit else text


def summarize_judgment(judgment_name, content):
    prompt = f"""קרא את פסק הדין הבא (הכתוב בעברית), וכתוב תקציר מסודר, תמציתי, ומקצועי של פסק הדין הכולל את כל הפרטים המשפטיים המרכזיים.
אנא כלול בתקציר את המידע הבא, במבנה ברור:

צדדים במשפט – מי הם הצדדים (לדוגמה: מדינת ישראל נגד פלוני).

נושא התיק – מה הנושא המרכזי של פסק הדין (לדוגמה: תקיפה, חוזה, לשון הרע, תכנון ובנייה וכו').

הצדדים שטענו ומה היו הטענות המרכזיות – מה טענה התביעה? מה טענה ההגנה? אילו עובדות מרכזיות הוצגו?

על אילו חוקים, תקנות או עקרונות משפטיים התבסס בית המשפט – ציין שמות סעיפים וחוקים אם מופיעים.

האם הוזכרו תקדימים משפטיים – ואם כן, מהם? (לרבות ציון מס' תיק או שמות תיקים)

מה פסק הדין הסופי – מי זכה במשפט? (תובע או נתבע? האם נדחה הערעור? האם בוטל כתב האישום?)

מה הייתה ההנמקה המרכזית של השופט/ת?

כתוב את התקציר בצורה מקצועית, ברורה, בעברית תקינה, וללא שיפוטיות.
אנא אל תמציא מידע שלא מופיע בפסק הדין.

בתוך מה שאני שולח
קח עד 1000 מילים.

פסק הדין: {judgment_name}

המידע:
{content}"""
    response = openai_client.chat.completions.create(
        model="gpt-3.5-turbo",
        messages=[{"role": "user", "content": prompt}],
        temperature=0.7
    )
    return response.choices[0].message.content.strip()


BATCH_SIZE = 5
docs = list(collection.find({"Description": {"$exists": False}}, {"Name": 1, "CaseNumber": 1, "segments": 1}))
total = len(docs)
print(f"Total documents to process: {total}")

for i in range(0, total, BATCH_SIZE):
    batch = docs[i:i + BATCH_SIZE]
    bulk_ops = []
    for doc in batch:
        judgment_name = doc.get("Name", "")
        segments = doc.get("segments", [])
        combined_text = " ".join(segments)
        trimmed_text = trim_to_word_limit(combined_text, limit=1000)
        summary = summarize_judgment(judgment_name, trimmed_text)
        bulk_ops.append(
            UpdateOne({"CaseNumber": doc["CaseNumber"]}, {"$set": {"Description": summary}})
        )
        print(f"Updated judgment {doc['CaseNumber']} with summary.")
        time.sleep(0.5)
    if bulk_ops:
        result = collection.bulk_write(bulk_ops)
        print(f"Processed {min(i + BATCH_SIZE, total)} / {total}")
    time.sleep(0.5)
