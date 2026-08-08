# app/services/faq_knowledge_base.py
"""
Static site FAQ / navigation knowledge base.

This is hand-maintained reference content — NOT generated from the DB and
NOT embedded/searched via pgvector. At this scale (a few dozen entries max),
just injecting the whole thing into the system prompt is simpler and more
reliable than building a retrieval step for it, and Claude is very good at
picking the relevant parts out of a modest block of reference text on its
own. Revisit with embedding-based retrieval only if this genuinely grows
too large to fit comfortably in a prompt (hundreds of entries).

IMPORTANT: The content below is placeholder/example content. Replace it
with your platform's actual policies before shipping — wrong answers about
refunds or payments from a chatbot are a real support liability, not just
a UX nitpick.
"""

FAQ_ENTRIES = [
    {
        "category": "Account & Enrollment",
        "question": "How do I enroll in a course?",
        "answer": (
            "Navigate to the course page and click 'Enroll'. If it's a paid course, "
            "you'll be taken through checkout first; enrollment is confirmed immediately "
            "after payment succeeds."
        ),
    },
    {
        "category": "Account & Enrollment",
        "question": "Can I access a course after I've finished it?",
        "answer": "Yes — enrollment gives lifetime access to the course content, including future updates the instructor makes to it.",
    },
    {
        "category": "Payments & Refunds",
        "question": "What is the refund policy?",
        "answer": (
            "[PLACEHOLDER — replace with your actual policy] Refunds are available "
            "within 14 days of purchase if less than 20% of the course has been completed."
        ),
    },
    {
        "category": "Payments & Refunds",
        "question": "What payment methods are accepted?",
        "answer": "[PLACEHOLDER — replace with your actual payment methods] Credit/debit cards and PayPal.",
    },
    {
        "category": "Instructors",
        "question": "Can I message an instructor directly?",
        "answer": "[PLACEHOLDER — confirm if this feature exists] Each course page has a Q&A section where you can post questions the instructor can respond to.",
    },
    {
        "category": "Instructors",
        "question": "How do I become an instructor on the platform?",
        "answer": "[PLACEHOLDER — replace with your actual application process/link]",
    },
    {
        "category": "Certificates",
        "question": "Do I get a certificate after completing a course?",
        "answer": "[PLACEHOLDER — confirm if this feature exists] Yes, a certificate of completion is issued automatically once all course material is marked complete.",
    },
    {
        "category": "Technical",
        "question": "The video player isn't loading — what should I do?",
        "answer": "Try refreshing the page or switching browsers first. If the issue persists, contact support with the course name and a screenshot of the error.",
    },
    {
        "category": "Recommendations",
        "question": "How does the platform decide what courses to recommend me?",
        "answer": (
            "Recommendations are based on your enrollment history — courses by "
            "instructors you've already learned from, and courses similar in "
            "content to ones you've taken."
        ),
    },
]


def format_faq_for_prompt() -> str:
    """
    Formats all FAQ entries into a single block of text suitable for
    inclusion in the chatbot's system prompt. Grouped by category so
    related entries stay visually together, which seems to help Claude
    stay grounded in the right section when answering.
    """
    by_category: dict[str, list[dict]] = {}
    for entry in FAQ_ENTRIES:
        by_category.setdefault(entry["category"], []).append(entry)

    sections = []
    for category, entries in by_category.items():
        lines = [f"## {category}"]
        for entry in entries:
            lines.append(f"Q: {entry['question']}\nA: {entry['answer']}")
        sections.append("\n\n".join(lines))

    return "\n\n".join(sections)