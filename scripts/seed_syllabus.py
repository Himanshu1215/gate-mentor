import sqlite3
import json
import os

DB_PATH = os.path.join(os.path.dirname(__file__), "..", "data", "gate_mentor.db")

# ─────────────────────────────────────────────────────────────────────────────
# Full GATE DA (Data Science & AI) syllabus mapped to the Global Concept Registry.
# concept_id prefix -> subject:
#   PROB_* Probability & Statistics   LA_*  Linear Algebra
#   CALC_* Calculus & Optimization    DSA_* Programming, DS & Algorithms
#   DB_*   DBMS & Warehousing         ML_*  Machine Learning
#   AI_*   Artificial Intelligence
# Existing IDs (PROB_001-003, LA_001-002, ML_001-002) are kept stable so prior
# mastery rows still line up. prerequisites form the learning DAG.
# ─────────────────────────────────────────────────────────────────────────────
GATE_DA_SYLLABUS = [
    # ── Probability and Statistics ──────────────────────────────────────────
    {"concept_id": "PROB_001", "subject": "Probability and Statistics", "topic": "Probability", "subtopic": "Axioms of Probability",
     "prerequisites": [], "difficulty": 4, "importance_weight": 0.7, "est_learning_time_mins": 60, "est_revision_time_mins": 15},
    {"concept_id": "PROB_002", "subject": "Probability and Statistics", "topic": "Probability", "subtopic": "Conditional Probability",
     "prerequisites": ["PROB_001"], "difficulty": 6, "importance_weight": 0.8, "est_learning_time_mins": 90, "est_revision_time_mins": 20},
    {"concept_id": "PROB_003", "subject": "Probability and Statistics", "topic": "Probability", "subtopic": "Bayes Theorem",
     "prerequisites": ["PROB_002"], "difficulty": 8, "importance_weight": 1.0, "est_learning_time_mins": 120, "est_revision_time_mins": 30},
    {"concept_id": "PROB_004", "subject": "Probability and Statistics", "topic": "Random Variables", "subtopic": "Random Variables",
     "prerequisites": ["PROB_001"], "difficulty": 5, "importance_weight": 0.8, "est_learning_time_mins": 75, "est_revision_time_mins": 20},
    {"concept_id": "PROB_005", "subject": "Probability and Statistics", "topic": "Distributions", "subtopic": "Discrete Distributions (Bernoulli, Binomial, Poisson)",
     "prerequisites": ["PROB_004"], "difficulty": 6, "importance_weight": 0.8, "est_learning_time_mins": 90, "est_revision_time_mins": 25},
    {"concept_id": "PROB_006", "subject": "Probability and Statistics", "topic": "Distributions", "subtopic": "Continuous Distributions (Uniform, Exponential, Normal)",
     "prerequisites": ["PROB_004"], "difficulty": 6, "importance_weight": 0.9, "est_learning_time_mins": 90, "est_revision_time_mins": 25},
    {"concept_id": "PROB_007", "subject": "Probability and Statistics", "topic": "Statistics", "subtopic": "Expectation, Variance & Moments",
     "prerequisites": ["PROB_004"], "difficulty": 6, "importance_weight": 0.8, "est_learning_time_mins": 75, "est_revision_time_mins": 20},
    {"concept_id": "PROB_008", "subject": "Probability and Statistics", "topic": "Statistics", "subtopic": "Central Limit Theorem & Sampling",
     "prerequisites": ["PROB_006"], "difficulty": 7, "importance_weight": 0.7, "est_learning_time_mins": 90, "est_revision_time_mins": 20},
    {"concept_id": "PROB_009", "subject": "Probability and Statistics", "topic": "Inferential Statistics", "subtopic": "Confidence Intervals",
     "prerequisites": ["PROB_008"], "difficulty": 7, "importance_weight": 0.6, "est_learning_time_mins": 75, "est_revision_time_mins": 20},
    {"concept_id": "PROB_010", "subject": "Probability and Statistics", "topic": "Inferential Statistics", "subtopic": "Hypothesis Testing",
     "prerequisites": ["PROB_008"], "difficulty": 8, "importance_weight": 0.8, "est_learning_time_mins": 120, "est_revision_time_mins": 30},
    {"concept_id": "PROB_011", "subject": "Probability and Statistics", "topic": "Statistics", "subtopic": "Correlation & Regression",
     "prerequisites": ["PROB_007"], "difficulty": 6, "importance_weight": 0.7, "est_learning_time_mins": 75, "est_revision_time_mins": 20},

    # ── Linear Algebra ──────────────────────────────────────────────────────
    {"concept_id": "LA_001", "subject": "Linear Algebra", "topic": "Vector Spaces", "subtopic": "Vector Space & Subspace",
     "prerequisites": [], "difficulty": 5, "importance_weight": 0.7, "est_learning_time_mins": 90, "est_revision_time_mins": 20},
    {"concept_id": "LA_003", "subject": "Linear Algebra", "topic": "Matrices", "subtopic": "Matrix Operations & Types",
     "prerequisites": ["LA_001"], "difficulty": 4, "importance_weight": 0.7, "est_learning_time_mins": 60, "est_revision_time_mins": 15},
    {"concept_id": "LA_004", "subject": "Linear Algebra", "topic": "Matrices", "subtopic": "Determinant & Rank",
     "prerequisites": ["LA_003"], "difficulty": 6, "importance_weight": 0.8, "est_learning_time_mins": 75, "est_revision_time_mins": 20},
    {"concept_id": "LA_005", "subject": "Linear Algebra", "topic": "Matrices", "subtopic": "Systems of Linear Equations",
     "prerequisites": ["LA_004"], "difficulty": 6, "importance_weight": 0.8, "est_learning_time_mins": 90, "est_revision_time_mins": 20},
    {"concept_id": "LA_002", "subject": "Linear Algebra", "topic": "Matrices", "subtopic": "Eigenvalues & Eigenvectors",
     "prerequisites": ["LA_001"], "difficulty": 7, "importance_weight": 0.9, "est_learning_time_mins": 120, "est_revision_time_mins": 25},
    {"concept_id": "LA_006", "subject": "Linear Algebra", "topic": "Decompositions", "subtopic": "LU Decomposition",
     "prerequisites": ["LA_005"], "difficulty": 7, "importance_weight": 0.6, "est_learning_time_mins": 75, "est_revision_time_mins": 20},
    {"concept_id": "LA_007", "subject": "Linear Algebra", "topic": "Decompositions", "subtopic": "Singular Value Decomposition (SVD)",
     "prerequisites": ["LA_002"], "difficulty": 8, "importance_weight": 0.7, "est_learning_time_mins": 120, "est_revision_time_mins": 30},
    {"concept_id": "LA_008", "subject": "Linear Algebra", "topic": "Applications", "subtopic": "Projections & Least Squares",
     "prerequisites": ["LA_005"], "difficulty": 7, "importance_weight": 0.6, "est_learning_time_mins": 90, "est_revision_time_mins": 20},

    # ── Calculus and Optimization ───────────────────────────────────────────
    {"concept_id": "CALC_001", "subject": "Calculus and Optimization", "topic": "Calculus", "subtopic": "Functions, Limits & Continuity",
     "prerequisites": [], "difficulty": 4, "importance_weight": 0.6, "est_learning_time_mins": 60, "est_revision_time_mins": 15},
    {"concept_id": "CALC_002", "subject": "Calculus and Optimization", "topic": "Calculus", "subtopic": "Differentiation",
     "prerequisites": ["CALC_001"], "difficulty": 5, "importance_weight": 0.7, "est_learning_time_mins": 75, "est_revision_time_mins": 20},
    {"concept_id": "CALC_003", "subject": "Calculus and Optimization", "topic": "Calculus", "subtopic": "Maxima & Minima",
     "prerequisites": ["CALC_002"], "difficulty": 6, "importance_weight": 0.8, "est_learning_time_mins": 75, "est_revision_time_mins": 20},
    {"concept_id": "CALC_004", "subject": "Calculus and Optimization", "topic": "Calculus", "subtopic": "Taylor Series",
     "prerequisites": ["CALC_002"], "difficulty": 6, "importance_weight": 0.5, "est_learning_time_mins": 60, "est_revision_time_mins": 15},
    {"concept_id": "CALC_005", "subject": "Calculus and Optimization", "topic": "Calculus", "subtopic": "Integration",
     "prerequisites": ["CALC_002"], "difficulty": 5, "importance_weight": 0.6, "est_learning_time_mins": 75, "est_revision_time_mins": 20},
    {"concept_id": "CALC_006", "subject": "Calculus and Optimization", "topic": "Optimization", "subtopic": "Single-variable Optimization",
     "prerequisites": ["CALC_003"], "difficulty": 7, "importance_weight": 0.7, "est_learning_time_mins": 90, "est_revision_time_mins": 20},
    {"concept_id": "CALC_007", "subject": "Calculus and Optimization", "topic": "Optimization", "subtopic": "Gradients & Multivariate Optimization",
     "prerequisites": ["CALC_003"], "difficulty": 7, "importance_weight": 0.7, "est_learning_time_mins": 90, "est_revision_time_mins": 25},

    # ── Programming, Data Structures and Algorithms ─────────────────────────
    {"concept_id": "DSA_001", "subject": "Programming, DS & Algorithms", "topic": "Programming", "subtopic": "Python Programming Basics",
     "prerequisites": [], "difficulty": 3, "importance_weight": 0.7, "est_learning_time_mins": 90, "est_revision_time_mins": 20},
    {"concept_id": "DSA_002", "subject": "Programming, DS & Algorithms", "topic": "Algorithms", "subtopic": "Complexity Analysis (Big-O)",
     "prerequisites": ["DSA_001"], "difficulty": 5, "importance_weight": 0.7, "est_learning_time_mins": 60, "est_revision_time_mins": 15},
    {"concept_id": "DSA_003", "subject": "Programming, DS & Algorithms", "topic": "Data Structures", "subtopic": "Arrays & Strings",
     "prerequisites": ["DSA_001"], "difficulty": 4, "importance_weight": 0.6, "est_learning_time_mins": 60, "est_revision_time_mins": 15},
    {"concept_id": "DSA_004", "subject": "Programming, DS & Algorithms", "topic": "Data Structures", "subtopic": "Stacks & Queues",
     "prerequisites": ["DSA_003"], "difficulty": 5, "importance_weight": 0.6, "est_learning_time_mins": 60, "est_revision_time_mins": 15},
    {"concept_id": "DSA_005", "subject": "Programming, DS & Algorithms", "topic": "Data Structures", "subtopic": "Linked Lists",
     "prerequisites": ["DSA_003"], "difficulty": 5, "importance_weight": 0.6, "est_learning_time_mins": 60, "est_revision_time_mins": 15},
    {"concept_id": "DSA_006", "subject": "Programming, DS & Algorithms", "topic": "Data Structures", "subtopic": "Trees & Binary Search Trees",
     "prerequisites": ["DSA_004"], "difficulty": 6, "importance_weight": 0.7, "est_learning_time_mins": 90, "est_revision_time_mins": 20},
    {"concept_id": "DSA_007", "subject": "Programming, DS & Algorithms", "topic": "Data Structures", "subtopic": "Hashing",
     "prerequisites": ["DSA_003"], "difficulty": 6, "importance_weight": 0.6, "est_learning_time_mins": 60, "est_revision_time_mins": 15},
    {"concept_id": "DSA_008", "subject": "Programming, DS & Algorithms", "topic": "Algorithms", "subtopic": "Searching (Linear & Binary)",
     "prerequisites": ["DSA_002"], "difficulty": 5, "importance_weight": 0.7, "est_learning_time_mins": 60, "est_revision_time_mins": 15},
    {"concept_id": "DSA_009", "subject": "Programming, DS & Algorithms", "topic": "Algorithms", "subtopic": "Sorting Algorithms",
     "prerequisites": ["DSA_002"], "difficulty": 6, "importance_weight": 0.8, "est_learning_time_mins": 90, "est_revision_time_mins": 20},
    {"concept_id": "DSA_010", "subject": "Programming, DS & Algorithms", "topic": "Algorithms", "subtopic": "Graph Algorithms (BFS, DFS, Shortest Path)",
     "prerequisites": ["DSA_006"], "difficulty": 8, "importance_weight": 0.8, "est_learning_time_mins": 120, "est_revision_time_mins": 30},

    # ── Database Management and Warehousing ─────────────────────────────────
    {"concept_id": "DB_001", "subject": "Database Management and Warehousing", "topic": "Data Modeling", "subtopic": "ER Model",
     "prerequisites": [], "difficulty": 4, "importance_weight": 0.6, "est_learning_time_mins": 60, "est_revision_time_mins": 15},
    {"concept_id": "DB_002", "subject": "Database Management and Warehousing", "topic": "Relational Model", "subtopic": "Relational Algebra",
     "prerequisites": ["DB_001"], "difficulty": 6, "importance_weight": 0.7, "est_learning_time_mins": 90, "est_revision_time_mins": 20},
    {"concept_id": "DB_003", "subject": "Database Management and Warehousing", "topic": "Relational Model", "subtopic": "SQL",
     "prerequisites": ["DB_002"], "difficulty": 5, "importance_weight": 0.9, "est_learning_time_mins": 120, "est_revision_time_mins": 25},
    {"concept_id": "DB_004", "subject": "Database Management and Warehousing", "topic": "Design", "subtopic": "Normalization",
     "prerequisites": ["DB_002"], "difficulty": 7, "importance_weight": 0.8, "est_learning_time_mins": 90, "est_revision_time_mins": 20},
    {"concept_id": "DB_005", "subject": "Database Management and Warehousing", "topic": "Systems", "subtopic": "Transactions & Concurrency",
     "prerequisites": ["DB_003"], "difficulty": 7, "importance_weight": 0.6, "est_learning_time_mins": 90, "est_revision_time_mins": 20},
    {"concept_id": "DB_006", "subject": "Database Management and Warehousing", "topic": "Systems", "subtopic": "Indexing & File Organization",
     "prerequisites": ["DB_003"], "difficulty": 6, "importance_weight": 0.5, "est_learning_time_mins": 75, "est_revision_time_mins": 20},
    {"concept_id": "DB_007", "subject": "Database Management and Warehousing", "topic": "Warehousing", "subtopic": "Data Warehousing & Modeling",
     "prerequisites": ["DB_003"], "difficulty": 6, "importance_weight": 0.6, "est_learning_time_mins": 75, "est_revision_time_mins": 20},

    # ── Machine Learning ────────────────────────────────────────────────────
    {"concept_id": "ML_001", "subject": "Machine Learning", "topic": "Supervised Learning", "subtopic": "Linear Regression",
     "prerequisites": ["LA_001"], "difficulty": 5, "importance_weight": 0.8, "est_learning_time_mins": 90, "est_revision_time_mins": 20},
    {"concept_id": "ML_002", "subject": "Machine Learning", "topic": "Supervised Learning", "subtopic": "Naive Bayes Classifier",
     "prerequisites": ["PROB_003"], "difficulty": 6, "importance_weight": 0.8, "est_learning_time_mins": 90, "est_revision_time_mins": 20},
    {"concept_id": "ML_003", "subject": "Machine Learning", "topic": "Supervised Learning", "subtopic": "Logistic Regression",
     "prerequisites": ["ML_001"], "difficulty": 6, "importance_weight": 0.8, "est_learning_time_mins": 90, "est_revision_time_mins": 20},
    {"concept_id": "ML_004", "subject": "Machine Learning", "topic": "Supervised Learning", "subtopic": "Support Vector Machines",
     "prerequisites": ["ML_003"], "difficulty": 8, "importance_weight": 0.7, "est_learning_time_mins": 120, "est_revision_time_mins": 30},
    {"concept_id": "ML_005", "subject": "Machine Learning", "topic": "Supervised Learning", "subtopic": "Decision Trees",
     "prerequisites": ["PROB_001"], "difficulty": 6, "importance_weight": 0.7, "est_learning_time_mins": 90, "est_revision_time_mins": 20},
    {"concept_id": "ML_006", "subject": "Machine Learning", "topic": "Supervised Learning", "subtopic": "K-Nearest Neighbors",
     "prerequisites": ["PROB_001"], "difficulty": 5, "importance_weight": 0.6, "est_learning_time_mins": 60, "est_revision_time_mins": 15},
    {"concept_id": "ML_007", "subject": "Machine Learning", "topic": "Unsupervised Learning", "subtopic": "K-Means Clustering",
     "prerequisites": ["LA_001"], "difficulty": 6, "importance_weight": 0.7, "est_learning_time_mins": 90, "est_revision_time_mins": 20},
    {"concept_id": "ML_008", "subject": "Machine Learning", "topic": "Unsupervised Learning", "subtopic": "Principal Component Analysis (PCA)",
     "prerequisites": ["LA_007"], "difficulty": 8, "importance_weight": 0.8, "est_learning_time_mins": 120, "est_revision_time_mins": 30},
    {"concept_id": "ML_009", "subject": "Machine Learning", "topic": "Model Selection", "subtopic": "Bias-Variance & Regularization",
     "prerequisites": ["ML_001"], "difficulty": 7, "importance_weight": 0.7, "est_learning_time_mins": 90, "est_revision_time_mins": 20},
    {"concept_id": "ML_010", "subject": "Machine Learning", "topic": "Model Selection", "subtopic": "Cross-validation & Evaluation Metrics",
     "prerequisites": ["ML_001"], "difficulty": 6, "importance_weight": 0.7, "est_learning_time_mins": 75, "est_revision_time_mins": 20},
    {"concept_id": "ML_011", "subject": "Machine Learning", "topic": "Deep Learning", "subtopic": "Neural Networks & Backpropagation",
     "prerequisites": ["ML_003", "CALC_007"], "difficulty": 8, "importance_weight": 0.7, "est_learning_time_mins": 150, "est_revision_time_mins": 35},

    # ── Artificial Intelligence ─────────────────────────────────────────────
    {"concept_id": "AI_001", "subject": "Artificial Intelligence", "topic": "Search", "subtopic": "Uninformed Search (BFS, DFS, UCS)",
     "prerequisites": ["DSA_010"], "difficulty": 6, "importance_weight": 0.7, "est_learning_time_mins": 90, "est_revision_time_mins": 20},
    {"concept_id": "AI_002", "subject": "Artificial Intelligence", "topic": "Search", "subtopic": "Informed Search (A*, Heuristics)",
     "prerequisites": ["AI_001"], "difficulty": 7, "importance_weight": 0.7, "est_learning_time_mins": 90, "est_revision_time_mins": 20},
    {"concept_id": "AI_003", "subject": "Artificial Intelligence", "topic": "Logic", "subtopic": "Propositional Logic",
     "prerequisites": [], "difficulty": 5, "importance_weight": 0.6, "est_learning_time_mins": 75, "est_revision_time_mins": 20},
    {"concept_id": "AI_004", "subject": "Artificial Intelligence", "topic": "Logic", "subtopic": "First-Order / Predicate Logic",
     "prerequisites": ["AI_003"], "difficulty": 7, "importance_weight": 0.6, "est_learning_time_mins": 90, "est_revision_time_mins": 20},
    {"concept_id": "AI_005", "subject": "Artificial Intelligence", "topic": "Reasoning", "subtopic": "Reasoning under Uncertainty",
     "prerequisites": ["PROB_003"], "difficulty": 7, "importance_weight": 0.6, "est_learning_time_mins": 90, "est_revision_time_mins": 20},
    {"concept_id": "AI_006", "subject": "Artificial Intelligence", "topic": "Reasoning", "subtopic": "Bayesian Networks",
     "prerequisites": ["AI_005"], "difficulty": 8, "importance_weight": 0.6, "est_learning_time_mins": 120, "est_revision_time_mins": 30},
]


def seed_syllabus():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    # Rebuild the concepts registry cleanly (guarantees the exact column set),
    # but PRESERVE mastery_states so re-running never wipes a learner's progress.
    cursor.execute("DROP TABLE IF EXISTS concepts")
    cursor.execute("""
        CREATE TABLE concepts (
            concept_id TEXT PRIMARY KEY,
            subject TEXT,
            topic TEXT,
            subtopic TEXT,
            prerequisites TEXT,
            difficulty INTEGER,
            importance_weight REAL,
            est_learning_time_mins INTEGER,
            est_revision_time_mins INTEGER
        )
    """)

    for c in GATE_DA_SYLLABUS:
        cursor.execute("""
            INSERT INTO concepts
            (concept_id, subject, topic, subtopic, prerequisites, difficulty, importance_weight, est_learning_time_mins, est_revision_time_mins)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            c["concept_id"], c["subject"], c["topic"], c["subtopic"],
            json.dumps(c["prerequisites"]), c["difficulty"], c["importance_weight"],
            c["est_learning_time_mins"], c["est_revision_time_mins"]
        ))

    # mastery_states: create if missing, add a level-1 row for any NEW concept,
    # leave existing progress untouched (INSERT OR IGNORE).
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS mastery_states (
            concept_id TEXT PRIMARY KEY,
            state_level INTEGER DEFAULT 1,
            accuracy REAL DEFAULT 0.0,
            last_revised TEXT,
            FOREIGN KEY(concept_id) REFERENCES concepts(concept_id)
        )
    """)
    for c in GATE_DA_SYLLABUS:
        cursor.execute(
            "INSERT OR IGNORE INTO mastery_states (concept_id, state_level, accuracy) VALUES (?, 1, 0.0)",
            (c["concept_id"],)
        )

    conn.commit()
    conn.close()
    print(f"Seeded {len(GATE_DA_SYLLABUS)} concepts across 7 GATE DA subjects "
          "(mastery progress preserved).")


if __name__ == "__main__":
    seed_syllabus()
