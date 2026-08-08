"""
Synthetic seed data generator.

Run with: uv run python -m app.db.seed

Populates instructors, courses, users, and enrollments with a deliberately
coherent structure (not random) so that:
  - instructor-based recommendations have something real to surface
  - content-based (embedding) recommendations have believable category
    clusters to learn from
  - Phase 2's embedding fine-tuning has enough same-category / cross-category
    signal to actually learn something, not just memorize 12 rows

This script is idempotent: it wipes existing rows (in FK-safe order) before
inserting fresh data, so it's safe to re-run any time during development.
"""

# import asyncio

# from sqlalchemy import delete

# from app.db.session import AsyncSessionLocal
# from app.models import Course, Enrollment, Instructor, User

# --- Raw source data -----------------------------------------------------
# Structured as plain dicts/tuples first, converted to model instances in
# seed(). Keeping the data separate from the insertion logic makes it easy
# to extend (add more courses/instructors) without touching the logic below.

INSTRUCTORS = [
    {"key": "ada", "name": "Ada Obi", "bio": "Full-stack developer and educator with 8 years teaching web development, specializing in JavaScript and React."},
    {"key": "chidi", "name": "Chidi Okafor", "bio": "Data scientist specializing in machine learning, statistics, and Python for data analysis."},
    {"key": "grace", "name": "Grace Adeyemi", "bio": "Product designer and UX researcher, formerly at two YC-backed startups."},
    {"key": "tunde", "name": "Tunde Bakare", "bio": "Cloud and DevOps engineer, AWS certified trainer with a focus on production infrastructure."},
    {"key": "ngozi", "name": "Ngozi Eze", "bio": "Digital marketing strategist specializing in SEO, content strategy, and paid acquisition."},
    {"key": "femi", "name": "Femi Alabi", "bio": "Backend engineer and educator focused on API design, databases, and system architecture."},
]

# Each course references its instructor by the "key" above.
COURSES = [
    # --- Web Development (Ada) ---
    {"instructor": "ada", "title": "JavaScript Fundamentals", "description": "Learn core JavaScript: variables, functions, closures, the DOM, and asynchronous programming from the ground up.", "category": "Web Development", "price": 49.99, "rating": 4.7},
    {"instructor": "ada", "title": "React for Beginners", "description": "Build modern, component-based web applications with React, hooks, and state management.", "category": "Web Development", "price": 59.99, "rating": 4.8},
    {"instructor": "ada", "title": "Advanced React Patterns", "description": "Context, custom hooks, performance optimization, and design patterns for large-scale React applications.", "category": "Web Development", "price": 69.99, "rating": 4.6},
    {"instructor": "ada", "title": "CSS and Responsive Design", "description": "Master modern CSS layout with Flexbox, Grid, and responsive design principles for all screen sizes.", "category": "Web Development", "price": 39.99, "rating": 4.5},
    # --- Data Science (Chidi) ---
    {"instructor": "chidi", "title": "Python for Data Science", "description": "Data analysis and visualization with Python, pandas, NumPy, and matplotlib for real-world datasets.", "category": "Data Science", "price": 64.99, "rating": 4.9},
    {"instructor": "chidi", "title": "Machine Learning Basics", "description": "Introduction to supervised and unsupervised learning, model evaluation, and scikit-learn fundamentals.", "category": "Data Science", "price": 69.99, "rating": 4.8},
    {"instructor": "chidi", "title": "Deep Learning with PyTorch", "description": "Neural networks, convolutional networks, and recurrent networks using PyTorch, from theory to implementation.", "category": "Data Science", "price": 79.99, "rating": 4.7},
    {"instructor": "chidi", "title": "Statistics for Data Analysis", "description": "Probability, hypothesis testing, and statistical inference for making sound data-driven decisions.", "category": "Data Science", "price": 54.99, "rating": 4.6},
    # --- Design (Grace) ---
    {"instructor": "grace", "title": "UI Design Principles", "description": "Learn layout, color theory, typography, and design systems used by professional product teams.", "category": "Design", "price": 44.99, "rating": 4.6},
    {"instructor": "grace", "title": "UX Research Fundamentals", "description": "User interviews, usability testing, and synthesizing research into actionable product decisions.", "category": "Design", "price": 49.99, "rating": 4.5},
    {"instructor": "grace", "title": "Figma for Product Design", "description": "Design interactive prototypes and reusable design systems using Figma's component and variant tools.", "category": "Design", "price": 39.99, "rating": 4.7},
    # --- Cloud & DevOps (Tunde) ---
    {"instructor": "tunde", "title": "AWS Cloud Practitioner", "description": "Foundational AWS services, cloud computing concepts, and certification exam preparation.", "category": "Cloud & DevOps", "price": 59.99, "rating": 4.6},
    {"instructor": "tunde", "title": "Docker and Kubernetes", "description": "Containerize applications with Docker and orchestrate them at scale with Kubernetes.", "category": "Cloud & DevOps", "price": 69.99, "rating": 4.8},
    {"instructor": "tunde", "title": "CI/CD Pipelines with GitHub Actions", "description": "Automate testing, building, and deployment workflows using GitHub Actions.", "category": "Cloud & DevOps", "price": 49.99, "rating": 4.5},
    # --- Marketing (Ngozi) ---
    {"instructor": "ngozi", "title": "SEO Fundamentals", "description": "Keyword research, on-page optimization, and link building strategies to rank higher in search results.", "category": "Marketing", "price": 44.99, "rating": 4.5},
    {"instructor": "ngozi", "title": "Content Marketing Strategy", "description": "Plan, create, and distribute content that builds audience trust and drives measurable growth.", "category": "Marketing", "price": 39.99, "rating": 4.6},
    {"instructor": "ngozi", "title": "Paid Advertising with Google & Meta Ads", "description": "Run profitable ad campaigns across Google and Meta platforms, from targeting to budget optimization.", "category": "Marketing", "price": 54.99, "rating": 4.4},
    # --- Backend / Systems (Femi) ---
    {"instructor": "femi", "title": "Node.js and Express APIs", "description": "Build REST APIs with Node.js, Express, and MongoDB, including authentication and error handling.", "category": "Web Development", "price": 54.99, "rating": 4.6},
    {"instructor": "femi", "title": "Database Design Fundamentals", "description": "Relational database design, normalization, indexing, and query optimization for production systems.", "category": "Backend & Systems", "price": 49.99, "rating": 4.7},
    {"instructor": "femi", "title": "System Design Interview Prep", "description": "Learn to design scalable systems: load balancing, caching, database sharding, and distributed architecture.", "category": "Backend & Systems", "price": 74.99, "rating": 4.8},
]

USERS = [
    {"key": "user_1", "name": "Bola Ade", "email": "bola.ade@example.com"},
    {"key": "user_2", "name": "David Umeh", "email": "david.umeh@example.com"},
    {"key": "user_3", "name": "Funmi Lawal", "email": "funmi.lawal@example.com"},
    {"key": "user_4", "name": "Ifeanyi Chukwu", "email": "ifeanyi.chukwu@example.com"},
    {"key": "user_5", "name": "Kemi Johnson", "email": "kemi.johnson@example.com"},
]

# Enrollments as (user_key, course_title) pairs — deliberately clustered so
# each user has a believable "interest area" plus one cross-category course,
# which is realistic and gives recommendations something to actually work with.
ENROLLMENTS = [
    # user_1: web dev track
    ("user_1", "JavaScript Fundamentals"),
    ("user_1", "React for Beginners"),
    ("user_1", "CSS and Responsive Design"),
    # user_2: data science track
    ("user_2", "Python for Data Science"),
    ("user_2", "Machine Learning Basics"),
    ("user_2", "Statistics for Data Analysis"),
    # user_3: design track + one cross-over into web dev
    ("user_3", "UI Design Principles"),
    ("user_3", "Figma for Product Design"),
    ("user_3", "React for Beginners"),
    # user_4: cloud/devops track
    ("user_4", "AWS Cloud Practitioner"),
    ("user_4", "Docker and Kubernetes"),
    # user_5: marketing track + backend cross-over
    ("user_5", "SEO Fundamentals"),
    ("user_5", "Content Marketing Strategy"),
    ("user_5", "Node.js and Express APIs"),
]


# async def seed() -> None:
#     async with AsyncSessionLocal() as session:
#         # Wipe in FK-safe order: children before parents.
#         await session.execute(delete(Enrollment))
#         await session.execute(delete(Course))
#         await session.execute(delete(Instructor))
#         await session.execute(delete(User))
#         await session.commit()

#         # Insert instructors, keep a key -> ORM object map for course FK linking.
#         instructor_map: dict[str, Instructor] = {}
#         for data in INSTRUCTORS:
#             instructor = Instructor(name=data["name"], bio=data["bio"])
#             session.add(instructor)
#             instructor_map[data["key"]] = instructor
#         await session.flush()  # assigns generated UUIDs without committing yet

#         # Insert courses, linking via the `instructor` relationship — SQLAlchemy
#         # fills in instructor_id automatically from the related object.
#         course_map: dict[str, Course] = {}
#         for data in COURSES:
#             course = Course(
#                 title=data["title"],
#                 description=data["description"],
#                 category=data["category"],
#                 price=data["price"],
#                 rating=data["rating"],
#                 instructor=instructor_map[data["instructor"]],
#             )
#             session.add(course)
#             course_map[data["title"]] = course
#         await session.flush()

#         # Insert users.
#         user_map: dict[str, User] = {}
#         for data in USERS:
#             user = User(name=data["name"], email=data["email"])
#             session.add(user)
#             user_map[data["key"]] = user
#         await session.flush()

#         # Insert enrollments, linking via relationships the same way.
#         for user_key, course_title in ENROLLMENTS:
#             enrollment = Enrollment(
#                 user=user_map[user_key],
#                 course=course_map[course_title],
#             )
#             session.add(enrollment)

#         await session.commit()

#     print(
#         f"Seeded {len(INSTRUCTORS)} instructors, {len(COURSES)} courses, "
#         f"{len(USERS)} users, {len(ENROLLMENTS)} enrollments."
#     )


# if __name__ == "__main__":
#     asyncio.run(seed())