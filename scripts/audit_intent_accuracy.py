import json
from app.config import settings
from app.embeddings.encoder import init_encoder
from app.retrieval.intent_classifier import get_intent_classifier

init_encoder(settings.embedding_model)
classifier = get_intent_classifier()

with open("data/evaluation/synthetic_qa.json", "r", encoding="utf-8") as f:
    data = json.load(f)

print(f"Total queries: {len(data)}")
correct_count = 0
correct_raw_count = 0

for item in data:
    q = item["query"]
    gt = item["intent"]
    res = classifier.classify(q)
    # Check what the raw best intent would have been if not flagged LOW_CONFIDENCE
    is_correct = (res.intent == gt)
    if is_correct:
        correct_count += 1
    print(f"[{item['id']}] '{q[:35]}' -> Expected: {gt:20} | Predicted: {res.intent:15} | Conf: {res.confidence:.2f} | Match: {is_correct}")

print(f"\nFinal Intent Accuracy (with threshold): {correct_count}/{len(data)} = {correct_count/len(data):.2%}")
