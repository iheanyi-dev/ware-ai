"""
Synthetic training data generator (Phase 2).

Run with: python scripts/generate_synthetic_training_data.py

Generates a LARGE (~hundreds of records), template-based synthetic dataset
of course-like title/description pairs, grouped by category. This is
DIFFERENT from app/db/seed_data.py:

  - seed_data.py (~20 courses)  -> used to test the actual app/API/pgvector
  - this script (~hundreds)     -> used ONLY to fine-tune the embedding
                                    model in Colab; never loaded into the
                                    real database

The categories here intentionally match seed_data.py's categories exactly
("Web Development", "Data Science", "Design", "Cloud & DevOps", "Marketing",
"Backend & Systems") so the model learns clustering behavior for the
taxonomy your real courses actually use.

Purely offline: no API calls, no DB connection, stdlib only.
"""

import json
import random
from pathlib import Path

# Reproducible output — re-running this script gives the same dataset,
# which matters if we want to compare training runs later.
random.seed(42)

OUTPUT_PATH = Path("data/training_data_synthetic.json")

# Target number of unique records to generate per category. Bump this up
# if the fine-tuned model underperforms and you want more training signal.
RECORDS_PER_CATEGORY = 60

# --- Word banks -----------------------------------------------------------
# Each category has its own list of concrete subtopics — this is what does
# the real work of making records "belong" together semantically. The
# other lists (audiences, descriptors, skill verbs) are shared/generic and
# just add natural-sounding variety around the subtopic.

CATEGORY_SUBTOPICS = {
    "Web Development": [
        "JavaScript", "TypeScript", "React", "Vue.js", "Angular", "Node.js",
        "Express.js", "HTML and CSS", "Responsive Web Design", "REST APIs",
        "GraphQL", "Web Accessibility", "Progressive Web Apps", "Next.js",
        "Tailwind CSS", "Frontend Testing", "Web Performance Optimization",
        "Browser DevTools", "Single Page Applications", "WebSockets",
    ],
    "Data Science": [
        "Python for Data Analysis", "Machine Learning", "Deep Learning",
        "Data Visualization", "Statistics", "Pandas and NumPy",
        "Natural Language Processing", "Computer Vision", "PyTorch",
        "TensorFlow", "Feature Engineering", "Time Series Analysis",
        "A/B Testing", "SQL for Data Science", "Data Cleaning",
        "Predictive Modeling", "Neural Networks", "Big Data with Spark",
    ],
    "Design": [
        "UI Design", "UX Research", "Figma", "Design Systems",
        "Typography", "Color Theory", "Wireframing and Prototyping",
        "Interaction Design", "Usability Testing", "Mobile App Design",
        "Design Thinking", "Accessibility in Design", "Branding and Identity",
        "Motion Design", "Design Critique and Feedback",
    ],
    "Cloud & DevOps": [
        "AWS", "Docker", "Kubernetes", "CI/CD Pipelines", "Terraform",
        "GitHub Actions", "Cloud Architecture", "Infrastructure as Code",
        "Linux System Administration", "Monitoring and Observability",
        "Site Reliability Engineering", "Azure Fundamentals",
        "Google Cloud Platform", "Serverless Computing", "Container Orchestration",
    ],
    "Marketing": [
        "SEO", "Content Marketing", "Google Ads", "Meta Ads",
        "Email Marketing", "Social Media Strategy", "Marketing Analytics",
        "Brand Strategy", "Growth Marketing", "Copywriting",
        "Conversion Rate Optimization", "Influencer Marketing",
        "Marketing Automation", "Affiliate Marketing",
    ],
    "Backend & Systems": [
        "Database Design", "System Design", "API Design", "Microservices",
        "Distributed Systems", "Caching Strategies", "Message Queues",
        "Database Indexing and Optimization", "Authentication and Authorization",
        "Load Balancing", "Event-Driven Architecture", "SQL Query Optimization",
        "Scalable Backend Architecture", "gRPC",
    ],
}

AUDIENCES = [
    "beginners", "working professionals", "aspiring developers",
    "career switchers", "students", "self-taught learners",
    "experienced practitioners", "small business owners",
]

DESCRIPTORS = [
    "comprehensive", "hands-on", "practical", "beginner-friendly",
    "in-depth", "project-based", "industry-focused", "step-by-step",
    "up-to-date", "career-focused",
]

SKILL_VERBS = ["Build", "Master", "Learn", "Create", "Develop", "Understand", "Explore"]

# --- Templates --------------------------------------------------------
# Title and description templates are kept separate and combined randomly,
# so the same subtopic can produce many non-identical records.

TITLE_TEMPLATES = [
    "{subtopic} for {audience}",
    "Mastering {subtopic}",
    "Introduction to {subtopic}",
    "{descriptor_cap} {subtopic} Bootcamp",
    "{subtopic} Fundamentals",
    "Advanced {subtopic} Techniques",
    "The Complete {subtopic} Course",
    "{subtopic}: From Zero to Job-Ready",
    "Practical {subtopic} for {audience}",
    "{subtopic} Crash Course",
]

DESCRIPTION_TEMPLATES = [
    "{skill} {subtopic} through {descriptor} lessons designed for {audience}, covering real-world projects and practical exercises.",
    "A {descriptor} course that teaches you {subtopic}, with a focus on the skills {audience} need to succeed.",
    "{skill} the core concepts of {subtopic} step by step, with {descriptor} examples tailored for {audience}.",
    "This course helps {audience} get hands-on with {subtopic} using {descriptor} projects and real industry scenarios.",
    "Everything {audience} need to know about {subtopic}, taught through {descriptor}, project-based lessons.",
    "{skill} {subtopic} from the ground up in this {descriptor} course built for {audience}.",
]


def generate_category_records(category: str, subtopics: list[str], count: int) -> list[dict]:
    """
    Generates `count` unique (by title) synthetic records for one category
    by randomly combining subtopics with title/description templates and
    word-bank fillers.
    """
    records: list[dict] = []
    seen_titles: set[str] = set()

    # Safety cap so we can't infinite-loop if the combination space for a
    # category is smaller than `count` (unlikely at these list sizes, but
    # cheap to guard against).
    max_attempts = count * 20
    attempts = 0

    while len(records) < count and attempts < max_attempts:
        attempts += 1

        subtopic = random.choice(subtopics)
        audience = random.choice(AUDIENCES)
        descriptor = random.choice(DESCRIPTORS)
        skill = random.choice(SKILL_VERBS)

        title = random.choice(TITLE_TEMPLATES).format(
            subtopic=subtopic,
            audience=audience,
            descriptor_cap=descriptor.capitalize(),
        )

        if title in seen_titles:
            continue  # try a different random combination

        description = random.choice(DESCRIPTION_TEMPLATES).format(
            subtopic=subtopic,
            audience=audience,
            descriptor=descriptor,
            skill=skill,
        )

        seen_titles.add(title)
        records.append(
            {
                "title": title,
                "description": description,
                "category": category,
            }
        )

    return records


def generate_dataset() -> list[dict]:
    dataset: list[dict] = []
    for category, subtopics in CATEGORY_SUBTOPICS.items():
        dataset.extend(generate_category_records(category, subtopics, RECORDS_PER_CATEGORY))
    return dataset


def main() -> None:
    dataset = generate_dataset()

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_PATH.write_text(json.dumps(dataset, indent=2), encoding="utf-8")

    category_counts: dict[str, int] = {}
    for record in dataset:
        category_counts[record["category"]] = category_counts.get(record["category"], 0) + 1

    print(f"Generated {len(dataset)} synthetic training records -> {OUTPUT_PATH}")
    print("Records per category:")
    for category, count in sorted(category_counts.items()):
        print(f"  {category}: {count}")


if __name__ == "__main__":
    main()