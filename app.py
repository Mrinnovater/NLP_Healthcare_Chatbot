import streamlit as st
import json
import re
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

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

# Streamlit UI
def chatbot():
    st.set_page_config(page_title="Healthcare Chatbot", page_icon="🧑‍⚕️", layout="centered")

    if "messages" not in st.session_state:
        st.session_state["messages"] = []

    if "name" not in st.session_state:
        st.session_state["name"] = None

    def add_message(message, sender):
        st.session_state.messages.append({"message": message, "sender": sender})

    def display_chat():
        for message in st.session_state.messages:
            if message["sender"] == "user":
                st.markdown(f"**🧑‍💻 {message['message']}**")
            else:
                st.markdown(f"**🧑‍⚕️ {message['message']}**")

    # Display chat history
    display_chat()

    # User input for chat
    user_input = st.text_input("Type your message here...", "")
    if user_input:
        add_message(user_input, "user")

        # Process message
        msg = user_input.strip().lower()

        exit_keywords = [
            "bye", "goodbye", "thank you", "thanks", "see you",
            "exit", "quit", "talk to you later", "that's all", "done", "ok bye"
        ]
        
        if any(kw in msg for kw in exit_keywords):
            goodbye = f"👋 Take care, {st.session_state['name']}! Wishing you good health. Goodbye!" if st.session_state["name"] else "👋 Take care! Wishing you good health. Goodbye!"
            add_message(goodbye, "bot")
            st.session_state["messages"] = []
            return

        name_match = re.search(r"(?:i\s*am|i'm|this is|my name is|iam)\s+([a-zA-Z]+)", msg, re.IGNORECASE)
        if name_match:
            name = name_match.group(1).capitalize()
            st.session_state["name"] = name
            add_message(f"😊 Nice to meet you, {name}! How can I assist you today?", "bot")
            return

        if msg in ["hello", "hi", "hai"]:
            greeting = "👋 Hello!"
            if st.session_state["name"]:
                greeting += f" How can I help you today, {st.session_state['name']}?"
            else:
                greeting += " How can I help you today?"
            add_message(greeting, "bot")
            return

        if st.session_state["awaiting"] == "age":
            try:
                st.session_state["age"] = int(msg)
                st.session_state["awaiting"] = "gender"
                add_message("🚻 Please enter your gender (male/female):", "bot")
                return
            except:
                add_message("❌ Please enter a valid age.", "bot")
                return

        if st.session_state["awaiting"] == "gender":
            if msg in ["male", "female"]:
                st.session_state["gender"] = msg
                age_group = get_age_group(st.session_state["age"])

                for disease in health_data["diseases"]:
                    if disease["disease"] == st.session_state["disease"]:
                        for dtype in disease["types"]:
                            if dtype["type"] == st.session_state["type"]:
                                for level in dtype["levels"]:
                                    if level["severity"] == st.session_state["severity"]:
                                        for group in level["groups"]:
                                            if group["age_group"] == age_group and group["gender"] == st.session_state["gender"]:
                                                reply = (
                                                    f"🩺 Diagnosis: <b>{st.session_state['disease']} ({st.session_state['type']})</b><br>"
                                                    f"🔺 Severity: <b>{st.session_state['severity'].capitalize()}</b><br>"
                                                    f"🎂 Age: {st.session_state['age']} | Gender: {st.session_state['gender'].capitalize()}<br><br>"
                                                    f"💊 <b>Medicine:</b> {group['medicine']}<br>"
                                                    f"📏 <b>Dosage:</b> {group['dosage']}<br>"
                                                    f"🥗 <b>Diet:</b> {group['diet']}<br>"
                                                    f"⚠️ <b>Precautions:</b> {group['precautions']}<br><br>"
                                                    f"📌 <i>Note: Always consult a doctor before taking any medicine.</i>"
                                                )
                                                add_message(reply, "bot")
                                                st.session_state["messages"] = []
                                                return

                add_message("⚠️ No specific recommendation for this age/gender group. Please consult a doctor.", "bot")
                return
            else:
                add_message("❌ Please enter gender as 'male' or 'female'.", "bot")
                return

        # Step 1: Rule-based symptom detection
        detected = [s for s in all_symptoms if s in msg and s not in st.session_state["symptoms"]]
        st.session_state["symptoms"].extend(detected)

        result = find_matching_disease(st.session_state["symptoms"])

        # Step 2: Use TF-IDF + Cosine Similarity if rule-based fails
        if not result:
            result = match_disease_tfidf(msg)

        if result:
            st.session_state["disease"] = result["disease"]
            st.session_state["type"] = result["type"]
            st.session_state["severity"] = result["severity"]
            st.session_state["awaiting"] = "age"
            add_message(f"✅ Detected disease: <b>{st.session_state['disease']} ({st.session_state['type']})</b><br>"
                        f"❗ Severity level: {st.session_state['severity'].capitalize()}<br>"
                        f"🎂 Please enter your age:", "bot")
        elif detected:
            add_message(f"📝 Noted symptoms: {', '.join(st.session_state['symptoms'])}.<br>"
                        f"Please describe more symptoms.", "bot")
        else:
            add_message("❓ Please describe your symptoms clearly so I can assist you better.", "bot")

# Run the Streamlit app
if __name__ == "__main__":
    chatbot()
