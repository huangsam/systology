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


def get_words(text: str, multiplier: int = 1) -> list[str]:
    """Tokenize text into lowercase words (length >= 4)."""
    # Remove code blocks and shortcodes
    text = re.sub(r"```.*?```", " ", text, flags=re.DOTALL)
    text = re.sub(r"`.*?`", " ", text)
    text = re.sub(r"{{.*?}}", " ", text)

    # Extract words (at least 4 chars)
    words = re.findall(r"\b[a-z]{4,}\b", text.lower())
    res = [w for w in words if w not in STOP_WORDS]
    return res * multiplier


def collect_docs(content_dir: Path) -> tuple[list[dict], set[str]]:
    """Walk content and collect tags and tokenized words."""
    docs = []
    global_tags = set()

    for p in content_dir.rglob(f"*{MD_EXT}"):
        if p.name.startswith(".") or p.name == "_index.md":
            continue

        try:
            text = p.read_text(encoding="utf-8")
        except Exception:
            continue

        fm_lines, body_lines = extract_fm_body(text)
        tags = parse_tags_from_text(text) if fm_lines is not None else []
        for t in tags:
            global_tags.add(t)

        # Meta weighting: prioritize core topics from frontmatter
        meta_text = ""
        if fm_lines:
            # Simple metadata extraction for weighting
            for line in fm_lines:
                if line.startswith("title:") or line.startswith("summary:"):
                    meta_text += " " + line.split(":", 1)[1]

        body_text = "\n".join(body_lines) if body_lines else ""
        words = get_words(body_text) + get_words(meta_text, multiplier=5)

        docs.append(
            {
                "path": p.relative_to(content_dir),
                "tags": set(tags),
                "words": words,
                "word_counts": Counter(words),
            }
        )
    return docs, global_tags


def report_tag_distribution(docs: list[dict]) -> None:
    """Analyze and print tag usage statistics and guideline adherence."""
    tag_counts = Counter()
    untagged = []
    overtagged = []

    for d in docs:
        for t in d["tags"]:
            tag_counts[t] += 1
        cnt = len(d["tags"])
        if cnt == 0:
            untagged.append(str(d["path"]))
        elif cnt > 5:
            overtagged.append((str(d["path"]), cnt))

    total_docs = len(docs)
    underused = [tag for tag, count in tag_counts.items() if count == 1]
    overused = [tag for tag, count in tag_counts.items() if count > (total_docs * 0.25)]

    print(f"Stats: {total_docs} docs, {len(tag_counts)} unique tags")
    if underused:
        print("Underused (orphaned):", ", ".join(sorted(underused)))
    if overused:
        print("Overused (broad):", ", ".join(sorted(overused)))

    if untagged or overtagged:
        print("\nGuideline Warnings (Tag Density):")
        for p in sorted(untagged):
            print(f"  [MISSING] {p}: 0 tags (Recommend 3-5)")
        for p, count in sorted(overtagged):
            print(f"  [OVERFLOW] {p}: {count} tags (Recommend 3-5)")


def collect_tag_distribution(docs: list[dict]) -> dict:
    """Return tag distribution stats and guideline violations as structured data."""
    tag_counts = Counter()
    untagged = []
    overtagged = []

    for d in docs:
        for t in d["tags"]:
            tag_counts[t] += 1
        cnt = len(d["tags"])
        if cnt == 0:
            untagged.append(str(d["path"]))
        elif cnt > 5:
            overtagged.append({"path": str(d["path"]), "count": cnt})

    total_docs = len(docs)
    underused = sorted(t for t, c in tag_counts.items() if c == 1)
    overused = sorted(t for t, c in tag_counts.items() if c > (total_docs * 0.25))

    return {
        "total_docs": total_docs,
        "unique_tags": len(tag_counts),
        "underused": underused,
        "overused": overused,
        "guideline_violations": {
            "missing": sorted(untagged),
            "overflow": overtagged,
        },
    }


def report_tag_cooccurrence(docs: list[dict]) -> None:
    """Analyze and print tag co-occurrence (Jaccard Similarity)."""
    redundancies = collect_tag_cooccurrence(docs)
    if redundancies:
        print("Redundant (Jaccard >= 0.80):")
        for r in redundancies:
            print(f"  - {r['tag_a']} / {r['tag_b']} ({(r['jaccard'] * 100):.0f}%)")


def collect_tag_cooccurrence(docs: list[dict]) -> list[dict]:
    """Return redundant tag pairs (Jaccard >= 0.80) as structured data."""
    tag_to_docs: dict[str, set[int]] = defaultdict(set)
    for i, d in enumerate(docs):
        for t in d["tags"]:
            tag_to_docs[t].add(i)

    tags_list = list(tag_to_docs.keys())
    threshold = 0.80
    redundancies = []

    for i in range(len(tags_list)):
        for j in range(i + 1, len(tags_list)):
            tA, tB = tags_list[i], tags_list[j]
            docsA, docsB = tag_to_docs[tA], tag_to_docs[tB]
            intersection = len(docsA & docsB)
            union = len(docsA | docsB)
            if union > 0:
                jaccard = intersection / union
                if jaccard >= threshold:
                    redundancies.append(
                        {"tag_a": tA, "tag_b": tB, "jaccard": round(jaccard, 4)}
                    )

    return sorted(redundancies, key=lambda x: -x["jaccard"])


def report_tag_recommendations(docs: list[dict], global_tags: set[str]) -> None:
    """Analyze TF-IDF scores and print tag recommendations grouped by section."""
    recommendations = collect_tag_recommendations(docs, global_tags)
    if recommendations:
        print("\nRecommendations (Found [Existing] or New Candidates):")
        sections = defaultdict(list)
        for path, recs in recommendations.items():
            section = path.split("/", 1)[0] if "/" in path else "other"
            sections[section].append((path, recs))

        for section in sorted(sections.keys()):
            print(f"  [{section.upper()}]")
            for path, recs in sorted(sections[section]):
                res_list = [f"[{t}]" for t in recs["established"]] + recs[
                    "new_candidates"
                ]
                print(f"    {path}: {', '.join(res_list)}")


def collect_tag_recommendations(docs: list[dict], global_tags: set[str]) -> dict:
    """Return TF-IDF tag recommendations as structured data keyed by file path."""
    total_docs = len(docs)
    df = Counter()
    for d in docs:
        for w in set(d["words"]):
            df[w] += 1

    recommendations: dict[str, dict] = {}
    for d in docs:
        doc_path = str(d["path"])
        doc_length = len(d["words"])
        if doc_length == 0:
            continue

        doc_scores = {}
        for w, tf in d["word_counts"].items():
            idf = math.log(total_docs / (1 + df[w]))
            doc_scores[w] = (tf / doc_length) * idf

        top_words = sorted(doc_scores.items(), key=lambda x: x[1], reverse=True)
        established_finds: set[str] = set()
        new_candidates: list[str] = []

        for t in global_tags:
            if t in d["tags"]:
                continue
            parts = t.split("-")
            if len(parts) > 1 and all(p in d["word_counts"] for p in parts):
                established_finds.add(t)

        for w, _ in top_words:
            if w in d["tags"] or w in established_finds:
                continue
            if w in global_tags:
                established_finds.add(w)
            elif df[w] >= 3:
                new_candidates.append(w)
            if len(established_finds) + len(new_candidates) >= 3:
                break

        if established_finds or new_candidates:
            recommendations[doc_path] = {
                "established": sorted(established_finds),
                "new_candidates": new_candidates,
            }

    return recommendations


def report_cross_references(docs: list[dict]) -> None:
    """Print a pre-computed cross-section tag-based linking map."""
    pairs = collect_cross_references(docs)
    if not pairs:
        return
    print("\nCross-References (Shared Tags Across Sections):")
    for entry in pairs:
        print(f"  {entry['a']} <-> {entry['b']}: {', '.join(entry['shared_tags'])}")


def collect_cross_references(docs: list[dict]) -> list[dict]:
    """Return cross-section document pairs and their shared tags as structured data."""
    tag_to_docs: dict[str, list[tuple[str, str]]] = defaultdict(list)
    for d in docs:
        doc_path = str(d["path"])
        section = doc_path.split("/", 1)[0] if "/" in doc_path else "other"
        for t in d["tags"]:
            tag_to_docs[t].append((section, doc_path))

    pair_tags: dict[tuple[str, str], set[str]] = defaultdict(set)
    for tag, entries in tag_to_docs.items():
        sections_present = {s for s, _ in entries}
        if len(sections_present) < 2:
            continue
        paths = [p for _, p in entries]
        for i in range(len(paths)):
            for j in range(i + 1, len(paths)):
                if entries[i][0] == entries[j][0]:
                    continue
                key = (min(paths[i], paths[j]), max(paths[i], paths[j]))
                pair_tags[key].add(tag)

    sorted_pairs = sorted(pair_tags.items(), key=lambda x: (-len(x[1]), x[0]))
    return [
        {"a": a, "b": b, "shared_tags": sorted(shared)}
        for (a, b), shared in sorted_pairs
    ]


def generate_insights(content_dir: Path, json_out: bool = False) -> None:
    """Run modular insights analysis and print reporting.

    Args:
        content_dir: Root content directory to scan.
        json_out: If True, emit a single JSON manifest instead of human-readable text.
    """
    import json as _json

    docs, global_tags = collect_docs(content_dir)

    if not docs:
        print("No markdown documents found.")
        return

    if json_out:
        manifest = {
            "stats": collect_tag_distribution(docs),
            "redundant_tags": collect_tag_cooccurrence(docs),
            "cross_references": collect_cross_references(docs),
            "recommendations": collect_tag_recommendations(docs, global_tags),
        }
        print(_json.dumps(manifest, indent=2))
        return

    report_tag_distribution(docs)
    report_tag_cooccurrence(docs)
    report_cross_references(docs)
    report_tag_recommendations(docs, global_tags)
