# **AI-Powered College Learning Assistant — Internship Assignment**

## **1\. Objective**

Build an **AI-powered learning assistant for college students** that can answer student queries by combining:

* Structured data from a PostgreSQL database  
* Unstructured course/learning content using RAG  
* Business rules implemented in the application  
* Student assessment and practice history

The goal is to build a **working AI application**, not just a basic chatbot.

---

## **2\. Provided Data**

You will be provided with:

### **Database**

A PostgreSQL database containing approximately:

* **30 interconnected tables**  
* **10,000 student records**  
* College and academic information  
* Student-course mappings  
* Courses and lessons  
* Assessments  
* Assessment questions  
* Student attempts  
* Student answers  
* Scores  
* Practice-question history  
* Course/lesson progress  
* Other relevant academic data

You are expected to understand the schema and identify the appropriate tables/data required for each use case.

### **Knowledge Base**

You will also be provided with course-related documents/content, such as:

* Course material  
* Lesson content  
* Topic explanations  
* Assessment information  
* Practice-question explanations  
* Academic guidelines

These should be used as the knowledge source for the RAG system.

---

# **3\. Core Requirement**

Build a chatbot where a student can ask questions such as:

> "Explain normalization from my DBMS course."

> "What is my current progress in Python?"

> "How did I perform in my previous assessments?"

> "What topics am I weak in?"

> "Can I attempt the Advanced Python assessment?"

> "Why am I not eligible for this assessment?"

> "Give me 5 practice questions based on the topics I am weak in."

> "Explain this topic based on the course material."

The system should determine **where the required information comes from**.

---

# **4\. Three Sources of Information**

The application must distinguish between the following:

### **A. Database**

Use the database for structured student/application information.

Examples:

* Student details  
* Enrolled courses  
* Course progress  
* Assessment attempts  
* Scores  
* Practice history  
* Completion status

---

### **B. RAG**

Use RAG for information contained in course/learning content.

Examples:

* Concept explanations  
* Course material  
* Lesson content  
* Topic descriptions  
* Examples  
* Learning resources

The RAG pipeline should include:

**Document → Chunking → Embedding → Vector Store → Retrieval → LLM → Response**

Answers generated from course content should provide appropriate source references.

---

### **C. Application Business Logic**

Some information will **not exist directly as a database field**.

Business rules will be provided separately and must be implemented in the application.

For example:

A student can attempt an assessment only when:  
\- The assessment is active  
\- Required course content is completed  
\- Required prerequisite assessment is passed  
\- Maximum attempt limit has not been reached

The AI must **not invent or independently determine these rules**.

It should call the appropriate application/business-logic function.

---

# **5\. AI Orchestration**

The assistant should determine which sources/tools are required to answer a question.

For example:

### **Question**

> "Can I take the Advanced SQL assessment, and what should I study?"

The system may need to:

1. Retrieve the student's SQL course progress from the database.  
2. Retrieve previous assessment attempts.  
3. Execute the assessment eligibility business rule.  
4. Identify weak SQL topics.  
5. Retrieve relevant SQL course content using RAG.  
6. Generate a personalized response.

The architecture should therefore separate:

AI Assistant  
     │  
     ├── Database/Data Services  
     │  
     ├── RAG  
     │  
     └── Business Logic  
---

# **6\. Database Access**

The LLM should **not have unrestricted access to the database**.

Create an appropriate data-access/tool layer.

Examples of possible tools/services:

getStudentCourseProgress()  
getAssessmentHistory()  
getStudentPerformance()  
getTopicPerformance()  
getCourseContent()  
checkAssessmentEligibility()  
getRecommendedTopics()

You may design these differently based on your architecture.

The important requirement is that database access and business rules remain controlled by the application.

---

# **7\. Student Performance**

The assistant should be able to analyse a student's learning history.

For example:

Student Performance

Python       82%  
SQL          64%  
DBMS         48%  
Java         76%

Weak Topics:  
\- SQL Joins  
\- Database Normalization  
\- Transactions

The system should use actual student data rather than generating fictional performance.

---

# **8\. Personalized Practice Questions**

Provide a feature to generate practice questions.

The student should be able to specify:

* Course  
* Topic  
* Difficulty  
* Number of questions

The system should use the relevant course content through RAG when generating questions.

Questions should include:

* Question  
* Options where applicable  
* Correct answer  
* Explanation

The system should avoid generating questions unrelated to the available course content.

---

# **9\. Business Rules**

You will be provided with a set of business rules.

You must:

* Understand the rules  
* Implement them in the application  
* Expose them through appropriate services/functions  
* Ensure the AI uses these functions when required

Do **not** place business rules inside prompts and assume the LLM will always follow them.

Business logic should be deterministic.

---

# **10\. Hallucination Handling**

The assistant must not confidently provide information that is unavailable.

For example, if a student asks:

> "What is the internal policy for X?"

and the information does not exist in the available knowledge base, the system should clearly indicate that sufficient information is unavailable.

Similarly, the assistant should not fabricate:

* Student scores  
* Course progress  
* Assessment eligibility  
* Course content  
* Business rules

---

# **11\. Minimum UI**

Build a simple web application with:

### **Chat**

* Student login/selection  
* Conversation interface  
* AI responses  
* Source references  
* Loading/error states

### **Performance**

* Course performance  
* Weak topics  
* Assessment history  
* Progress

### **Practice**

* Select course/topic  
* Select difficulty  
* Generate questions  
* Display answers/explanations

The UI does not need to be highly polished. **Functionality and engineering quality are more important.**

---

# **12\. Technical Expectations**

You may choose the technology stack.

You should be able to justify your choices for:

* LLM  
* Embedding model  
* Vector database  
* Backend framework  
* Database access  
* RAG framework, if any  
* Frontend framework

Do not simply use a framework without understanding what it is doing internally.

---

# **13\. Expected Architecture**

Design the architecture yourself, but it should broadly support:

                 Student  
                     │  
                     ▼  
              AI Learning Assistant  
                     │  
              Query / Intent Analysis  
                     │  
       ┌─────────────┼─────────────┐  
       ▼             ▼             ▼  
   Database         RAG       Business Logic  
       │             │             │  
       ▼             ▼             ▼  
 Student Data   Course Data    Application Rules  
       │             │             │  
       └─────────────┼─────────────┘  
                     ▼  
                 LLM Response

Submit an architecture diagram along with the project.

---

# **14\. Evaluation**

Create at least **20 test scenarios** covering:

* Database-based questions  
* RAG-based questions  
* Business-rule questions  
* Questions requiring multiple sources  
* Follow-up questions  
* Personalized questions  
* Missing information  
* Invalid/unauthorized requests  
* Assessment eligibility  
* Performance analysis

For each test, document:

Question  
Expected Behaviour  
Actual Behaviour  
Result  
---

# **15\. Deliverables**

Submit:

1. Working application  
2. Source code  
3. Database integration  
4. RAG pipeline  
5. Business-logic implementation  
6. AI/tool orchestration  
7. Student performance analysis  
8. Practice-question generation  
9. Architecture diagram  
10. Test cases and results  
11. README with setup instructions

---

## **Key Expectation**

This assignment is **not a "chat with PDF" project**.

The primary objective is to demonstrate that you can build an AI system that correctly combines:

**Structured data \+ unstructured knowledge \+ deterministic business logic \+ LLM reasoning**

while maintaining accuracy, security, and clear separation between these components.

