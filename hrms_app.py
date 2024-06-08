import streamlit as st
import requests
import openai
import re

# API URLs
JOB_API_URL = "https://x8ki-letl-twmt.n7.xano.io/api:2Yytv5FJ/job_desc"
CANDIDATE_API_URL = "https://x8ki-letl-twmt.n7.xano.io/api:2Yytv5FJ/candidate"
INTERVIEW_API_URL = "https://x8ki-letl-twmt.n7.xano.io/api:2Yytv5FJ/job_interview"

# Fetch job data from the API
def fetch_job_data():
    try:
        response = requests.get(JOB_API_URL)
        response.raise_for_status()
        return response.json()
    except requests.RequestException as e:
        st.error(f"Failed to fetch job data: {e}")
        return []

# Submit candidate data to the API
def submit_candidate(name, email):
    payload = {"name": name, "email": email}
    try:
        response = requests.post(CANDIDATE_API_URL, json=payload)
        response.raise_for_status()
        st.success("Application submitted successfully!")
        return response.json().get("id")
    except requests.RequestException as e:
        st.error(f"Failed to submit application: {e}")
        return None

# Submit interview data to the API
def submit_interview(candidate_id, job_desc_id, summary, interview_score):
    payload = {
        "candidate_id": candidate_id,
        "job_desc_id": job_desc_id,
        "summary": summary,
        "similarity_score": 0,
        "interview_score": interview_score
    }
    try:
        response = requests.post(INTERVIEW_API_URL, json=payload)
        response.raise_for_status()
        st.success("Interview results submitted successfully!")
    except requests.RequestException as e:
        st.error(f"Failed to submit interview results: {e}")

# Display job data and form in Streamlit
def display_jobs_and_form(jobs):
    st.title("Available Jobs")
    
    job_options = {job['role_name']: job for job in jobs}
    selected_job_name = st.selectbox("Select a job", list(job_options.keys()))
    selected_job = job_options[selected_job_name]
    
    st.write("### Job Description")
    st.write(selected_job['role_description'])
    
    st.subheader("Application Form")
    name = st.text_input("Name")
    email = st.text_input("Email")
    
    if st.button("Submit Application"):
        if name and email:
            candidate_id = submit_candidate(name, email)
            if candidate_id:
                st.session_state.update({
                    'selected_job': selected_job,
                    'candidate_name': name,
                    'candidate_email': email,
                    'candidate_id': candidate_id,
                    'current_question_index': 0,
                    'messages': [],
                    'interview_started': False
                })
                st.experimental_rerun()
        else:
            st.error("Please fill in all fields")

# Analyze responses and generate a summary and score
def analyze_responses(messages):
    responses = [{"role": "user", "content": msg["content"]} for msg in messages if msg["role"] == "user"]
    analysis_prompt = "Analyze the following interview responses and provide a summary. Also, give a score out of 100: in the format 'score out of 100:' or '|Score:' "
    analysis_response = openai.ChatCompletion.create(
        model=st.session_state["openai_model"],
        messages=[{"role": "system", "content": analysis_prompt}] + responses,
        max_tokens=500
    )
    analysis_text = analysis_response.choices[0].message["content"].strip()
    return analysis_text

# Extract score using regular expression
def extract_score(analysis_text):
    score_regex = r"score out of 100: (\d+)|Score: (\d+)"
    match = re.search(score_regex, analysis_text)
    if match:
        return int(match.group(1) or match.group(2))
    else:
        st.error("Failed to extract interview score. Analysis format might have changed.")
        return None

# Custom interview prompt
def generate_interview_prompt(candidate_name, job_description):
    return f"Imagine you are an HR interviewer who has dealt with hundreds of resume applications. I want you to ask 5 questions about the candidate's profile, background, experience, etc., based on the job description and candidate name below. Asking only one question at a time, for users to be able to answer the question one by one.\nJob Description: {job_description}\nCandidate Name: {candidate_name}\nStart with a personalized greeting, and explain a bit about the role, before you start asking questions to the candidate."

# Get next interview question using OpenAI
def get_next_interview_question(messages, candidate_name, job_description):
    prompt = generate_interview_prompt(candidate_name, job_description)
    response = openai.ChatCompletion.create(
        model=st.session_state["openai_model"],
        messages=[{"role": "system", "content": prompt}] + messages,
        max_tokens=150
    )
    return response.choices[0].message["content"].strip()

# Interview page
def interview_page():
    st.title("Interview Chatbot")

    openai.api_key = st.secrets["openai"]["OPENAI_API_KEY"]

    if "openai_model" not in st.session_state:
        st.session_state["openai_model"] = "gpt-3.5-turbo"

    # Define initial message
    initial_message = get_next_interview_question([], st.session_state["candidate_name"], st.session_state["selected_job"]["role_description"])

    # Display the chat messages
    for message in st.session_state.messages:
        with st.chat_message(message["role"]):
            st.markdown(message["content"])

    if not st.session_state.interview_started:
        st.session_state.messages.append({"role": "assistant", "content": initial_message})
        with st.chat_message("assistant"):
            st.markdown(initial_message)
        st.session_state.interview_started = True

    # Handle the chat input and responses
    if prompt := st.chat_input("Type your answer and press Enter"):
        st.session_state.messages.append({"role": "user", "content": prompt})
        with st.chat_message("user"):
            st.markdown(prompt)

        if st.session_state.current_question_index < 4:
            next_question = get_next_interview_question(st.session_state.messages, st.session_state["candidate_name"], st.session_state["selected_job"]["role_description"])
            st.session_state.messages.append({"role": "assistant", "content": next_question})
            st.session_state.current_question_index += 1
            with st.chat_message("assistant"):
                st.markdown(next_question)
        else:
            st.session_state.current_question_index += 1  # Update index to prevent further questions
            end_message = "Thank you for your time. We will get back to you soon."
            st.session_state.messages.append({"role": "assistant", "content": end_message})
            with st.chat_message("assistant"):
                st.markdown(end_message)

            # Analyze responses and save results
            analysis = analyze_responses(st.session_state.messages)
            summary = analysis.split("\n\n")[0]
            interview_score = extract_score(analysis)
            st.session_state.update({
                'summary': summary,
                'interview_score': interview_score
            })

            if interview_score is not None:
                submit_interview(
                    st.session_state.candidate_id,
                    st.session_state.selected_job['id'],
                    summary,
                    interview_score
                )

def main():
    if 'selected_job' in st.session_state and 'candidate_name' in st.session_state:
        interview_page()
    else:
        jobs = fetch_job_data()
        display_jobs_and_form(jobs)

if __name__ == "__main__":
    main()
