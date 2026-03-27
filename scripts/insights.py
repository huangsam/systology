"""
Logic for analyzing tag insights and generating optimization recommendations.
"""

import math
import re
from collections import Counter, defaultdict
from pathlib import Path

from scripts.constants import MD_EXT
from scripts.metadata import parse_tags_from_text
from scripts.utils import extract_fm_body

# A practical set of English stop words to ensure our TF-IDF doesn't just recommend "the" or "and"
STOP_WORDS = {
    "a",
    "about",
    "above",
    "after",
    "again",
    "against",
    "all",
    "am",
    "an",
    "and",
    "any",
    "are",
    "aren't",
    "as",
    "at",
    "be",
    "because",
    "been",
    "before",
    "being",
    "below",
    "between",
    "both",
    "but",
    "by",
    "can't",
    "cannot",
    "could",
    "couldn't",
    "did",
    "didn't",
    "do",
    "does",
    "doesn't",
    "doing",
    "don't",
    "down",
    "during",
    "each",
    "few",
    "for",
    "from",
    "further",
    "had",
    "hadn't",
    "has",
    "hasn't",
    "have",
    "haven't",
    "having",
    "he",
    "he'd",
    "he'll",
    "he's",
    "her",
    "here",
    "here's",
    "hers",
    "herself",
    "him",
    "himself",
    "his",
    "how",
    "how's",
    "i",
    "i'd",
    "i'll",
    "i'm",
    "i've",
    "if",
    "in",
    "into",
    "is",
    "isn't",
    "it",
    "it's",
    "its",
    "itself",
    "let's",
    "me",
    "more",
    "most",
    "mustn't",
    "my",
    "myself",
    "no",
    "nor",
    "not",
    "of",
    "off",
    "on",
    "once",
    "only",
    "or",
    "other",
    "ought",
    "our",
    "ours",
    "ourselves",
    "out",
    "over",
    "own",
    "same",
    "shan't",
    "she",
    "she'd",
    "she'll",
    "she's",
    "should",
    "shouldn't",
    "so",
    "some",
    "such",
    "than",
    "that",
    "that's",
    "the",
    "their",
    "theirs",
    "them",
    "themselves",
    "then",
    "there",
    "there's",
    "these",
    "they",
    "they'd",
    "they'll",
    "they're",
    "they've",
    "this",
    "those",
    "through",
    "to",
    "too",
    "under",
    "until",
    "up",
    "very",
    "was",
    "wasn't",
    "we",
    "we'd",
    "we'll",
    "we're",
    "we've",
    "were",
    "weren't",
    "what",
    "what's",
    "when",
    "when's",
    "where",
    "where's",
    "which",
    "while",
    "who",
    "who's",
    "whom",
    "why",
    "why's",
    "with",
    "won't",
    "would",
    "wouldn't",
    "you",
    "you'd",
    "you'll",
    "you're",
    "you've",
    "your",
    "yours",
    "yourself",
    "yourselves",
    # Technical noise
    "architecture",
    "provide",
    "within",
    "across",
    "using",
    "metadata",
    "based",
    "without",
    "level",
    "first",
    "single",
    "than",
    "while",
    "must",
    "requirements",
    "when",
    "like",
    "each",
    "into",
    "only",
    "also",
    "done",
    "made",
    "used",
    "will",
    "well",
    "implement",
    "deploy",
    "optimize",
    "system",
}


def get_words(text: str) -> list[str]:
    """Tokenize text into lowercase words (length >= 4)."""
    # Remove code blocks and shortcodes
    text = re.sub(r"```.*?```", " ", text, flags=re.DOTALL)
    text = re.sub(r"`.*?`", " ", text)
    text = re.sub(r"{{.*?}}", " ", text)

    # Extract words (at least 4 chars)
    words = re.findall(r"\b[a-z]{4,}\b", text.lower())
    return [w for w in words if w not in STOP_WORDS]


def generate_insights(content_dir: Path) -> None:
    """Run insights analysis and print minimal reporting."""
    docs = []
    global_tags = set()

    # Pass 1: Collect files, tags, and terms
    for p in content_dir.rglob(f"*{MD_EXT}"):
        if p.name.startswith("."):
            continue

        try:
            text = p.read_text(encoding="utf-8")
        except Exception:
            continue

        fm_lines, body_lines = extract_fm_body(text)
        tags = parse_tags_from_text(text) if fm_lines is not None else []
        for t in tags:
            global_tags.add(t)
        body_text = "\n".join(body_lines) if body_lines else ""
        words = get_words(body_text)

        docs.append(
            {
                "path": p.relative_to(content_dir),
                "tags": set(tags),
                "words": words,
                "word_counts": Counter(words),
            }
        )

    if not docs:
        print("No markdown documents found.")
        return

    # --- 1. Tag Distribution Analysis ---
    tag_counts = Counter()
    for d in docs:
        for t in d["tags"]:
            tag_counts[t] += 1

    total_docs = len(docs)
    underused = [tag for tag, count in tag_counts.items() if count == 1]
    overused = [tag for tag, count in tag_counts.items() if count > (total_docs * 0.25)]

    print(f"Stats: {total_docs} docs, {len(tag_counts)} unique tags")

    if underused:
        print("Underused (orphaned):", ", ".join(sorted(underused)))

    if overused:
        print("Overused (broad):", ", ".join(sorted(overused)))

    # --- 2. Tag Co-occurrence (Jaccard Similarity) ---
    tag_to_docs = defaultdict(set)
    for i, d in enumerate(docs):
        for t in d["tags"]:
            tag_to_docs[t].add(i)

    tags_list = list(tag_to_docs.keys())
    redundancies = []
    threshold = 0.80  # 80% overlap

    for i in range(len(tags_list)):
        for j in range(i + 1, len(tags_list)):
            tA = tags_list[i]
            tB = tags_list[j]
            docsA = tag_to_docs[tA]
            docsB = tag_to_docs[tB]

            intersection = len(docsA.intersection(docsB))
            union = len(docsA.union(docsB))

            if union > 0:
                jaccard = intersection / union
                if jaccard >= threshold:
                    redundancies.append((tA, tB, jaccard))

    if redundancies:
        print(f"Redundant (Jaccard > {threshold}):")
        for tA, tB, score in sorted(redundancies, key=lambda x: x[2], reverse=True):
            print(f"  - {tA} / {tB} ({(score * 100):.0f}%)")

    # --- 3. Tag Recommendations ---
    # Compute Document Frequency (DF) for each word
    df = Counter()
    for d in docs:
        for w in set(d["words"]):
            df[w] += 1

    recommendations = {}

    for d in docs:
        doc_path = str(d["path"])
        doc_length = len(d["words"])
        if doc_length == 0:
            continue

        doc_scores = {}
        for w, tf in d["word_counts"].items():
            idf = math.log(total_docs / (1 + df[w]))
            tfidf = (tf / doc_length) * idf
            doc_scores[w] = tfidf

        top_words = sorted(doc_scores.items(), key=lambda x: x[1], reverse=True)

        established_finds = set()
        new_candidates = []

        # Tier 1: Multi-word established tags
        for t in global_tags:
            if t in d["tags"]:
                continue
            parts = t.split("-")
            if len(parts) > 1 and all(p in d["word_counts"] for p in parts):
                established_finds.add(t)

        # Tier 2: Single-word established tags and new discovery
        for w, score in top_words:
            if w in d["tags"] or w in established_finds:
                continue

            if w in global_tags:
                established_finds.add(w)
            elif df[w] >= 3:
                new_candidates.append(w)

            if len(established_finds) + len(new_candidates) >= 3:
                break

        if established_finds or new_candidates:
            # Format: established tags in brackets
            res = [f"[{t}]" for t in sorted(list(established_finds))] + new_candidates
            recommendations[doc_path] = res

    if recommendations:
        print("\nRecommendations (Found [Existing] or New Candidates):")
        # Sorted by path for stability
        for path in sorted(recommendations.keys()):
            rec_list = recommendations[path]
            print(f"  {path}: {', '.join(rec_list)}")
