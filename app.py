from flask import Flask, render_template, request, jsonify
import json
import re
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

app = Flask(__name__)

# Load health dataset
with open("improved_health_dataset_with_realistic_medicines.json") as f:
    health_data = json.load(f)

# Collect all known symptoms
all_symptoms = set()
symptom_phrases = []
symptom_lookup = []

for disease in health_data["diseases"]:
    for dtype in disease["types"]:
        for level in dtype["levels"]:
            for group in level["groups"]:
                phrase = " ".join(group["symptoms"]).lower()
                symptom_phrases.append(phrase)
                symptom_lookup.append({
                    "disease": disease["disease"],
                    "type": dtype["type"],
                    "severity": level["severity"],
                    "group": group
                })
                all_symptoms.update(s.lower() for s in group["symptoms"])

# Build TF-IDF model
vectorizer = TfidfVectorizer()
tfidf_matrix = vectorizer.fit_transform(symptom_phrases)

# Global state
state = {
    "symptoms": [],
    "disease": None,
    "type": None,
    "severity": None,
    "age": None,
    "gender": None,
    "awaiting": None,
    "name": None
}

def get_age_group(age):
    if age <= 12:
        return "children"
    elif age <= 60:
        return "adults"
    return "oldage"

def find_matching_disease(user_symptoms):
    for disease in health_data["diseases"]:
        for dtype in disease["types"]:
            for level in dtype["levels"]:
                for group in level["groups"]:
                    if all(sym in user_symptoms for sym in group["symptoms"]):
                        return {
                            "disease": disease["disease"],
                            "type": dtype["type"],
                            "severity": level["severity"],
                            "group": group
                        }
    return None

def match_disease_tfidf(user_input):
    user_input_clean = re.sub(r'[^a-zA-Z\s]', '', user_input.lower())
    input_vector = vectorizer.transform([user_input_clean])
    similarities = cosine_similarity(input_vector, tfidf_matrix)
    best_match_idx = similarities.argmax()
    best_score = similarities[0][best_match_idx]
    if best_score > 0.2:
        return symptom_lookup[best_match_idx]
    return None

@app.route("/")
def index():
    return render_template("index.html")

@app.route("/chat", methods=["POST"])
def chat():
    msg = request.json["message"].strip().lower()

    exit_keywords = [
        "bye", "goodbye", "thank you", "thanks", "see you",
        "exit", "quit", "talk to you later", "that's all", "done", "ok bye"
    ]
    
    if any(kw in msg for kw in exit_keywords):
        user_name = state.get("name")
        goodbye = f"👋 Take care, {user_name.capitalize()}! Wishing you good health. Goodbye!" if user_name else "👋 Take care! Wishing you good health. Goodbye!"
        state.update({k: None if isinstance(v, str) else [] for k, v in state.items()})
        return jsonify({"reply": goodbye})

    name_match = re.search(r"(?:i\s*am|i'm|this is|my name is|iam)\s+([a-zA-Z]+)", msg, re.IGNORECASE)
    if name_match:
        name = name_match.group(1).capitalize()
        state["name"] = name
        return jsonify({"reply": f"😊 Nice to meet you, {name}! How can I assist you today?"})

    if msg in ["hello", "hi", "hai"]:
        greeting = "👋 Hello!"
        if state["name"]:
            greeting += f" How can I help you today, {state['name'].capitalize()}?"
        else:
            greeting += " How can I help you today?"
        return jsonify({"reply": greeting})

    if state["awaiting"] == "age":
        try:
            state["age"] = int(msg)
            state["awaiting"] = "gender"
            return jsonify({"reply": "🚻 Please enter your gender (male/female):"})
        except:
            return jsonify({"reply": "❌ Please enter a valid age."})

    if state["awaiting"] == "gender":
        if msg in ["male", "female"]:
            state["gender"] = msg
            age_group = get_age_group(state["age"])

            for disease in health_data["diseases"]:
                if disease["disease"] == state["disease"]:
                    for dtype in disease["types"]:
                        if dtype["type"] == state["type"]:
                            for level in dtype["levels"]:
                                if level["severity"] == state["severity"]:
                                    for group in level["groups"]:
                                        if group["age_group"] == age_group and group["gender"] == state["gender"]:
                                            reply = (
                                                f"🩺 Diagnosis: <b>{state['disease']} ({state['type']})</b><br>"
                                                f"🔺 Severity: <b>{state['severity'].capitalize()}</b><br>"
                                                f"🎂 Age: {state['age']} | Gender: {state['gender'].capitalize()}<br><br>"
                                                f"💊 <b>Medicine:</b> {group['medicine']}<br>"
                                                f"📏 <b>Dosage:</b> {group['dosage']}<br>"
                                                f"🥗 <b>Diet:</b> {group['diet']}<br>"
                                                f"⚠️ <b>Precautions:</b> {group['precautions']}<br><br>"
                                                f"📌 <i>Note: Always consult a doctor before taking any medicine.</i>"
                                            )
                                            state.update({k: None if isinstance(v, str) else [] for k, v in state.items()})
                                            return jsonify({"reply": reply})

            return jsonify({"reply": "⚠️ No specific recommendation for this age/gender group. Please consult a doctor."})
        else:
            return jsonify({"reply": "❌ Please enter gender as 'male' or 'female'."})

    # Step 1: Rule-based symptom detection
    detected = [s for s in all_symptoms if s in msg and s not in state["symptoms"]]
    state["symptoms"].extend(detected)

    result = find_matching_disease(state["symptoms"])

    # Step 2: Use TF-IDF + Cosine Similarity if rule-based fails
    if not result:
        result = match_disease_tfidf(msg)

    if result:
        state["disease"] = result["disease"]
        state["type"] = result["type"]
        state["severity"] = result["severity"]
        state["awaiting"] = "age"
        return jsonify({"reply": f"✅ Detected disease: <b>{state['disease']} ({state['type']})</b><br>"
                                 f"❗ Severity level: {state['severity'].capitalize()}<br>"
                                 f"🎂 Please enter your age:"})
    elif detected:
        return jsonify({"reply": f"📝 Noted symptoms: {', '.join(state['symptoms'])}.<br>"
                                 f"Please describe more symptoms."})

    return jsonify({"reply": "❓ Please describe your symptoms clearly so I can assist you better."})

if __name__ == "__main__":
    app.run(debug=True)
