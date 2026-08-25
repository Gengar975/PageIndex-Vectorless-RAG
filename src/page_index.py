import json
from pathlib import Path


def build_page_index(document, sections):
    page_index = {}

    for page in document.get("pages", []):
        number = page["page_number"]
        page_index[number] = {
            "page_number": number,
            "nodes": [],
        }

    for section in sections:
        start = section["start_page"]
        end = section["end_page"]

        for number in range(start, end + 1):
            if number not in page_index:
                continue

            node = {
                "id": section["id"],
                "type": section["type"],
                "heading": section["heading"],
                "pages": list(range(start, end + 1)),
            }

            relevant_subsections = []

            for subsection in section.get("subsections", []):
                ss = subsection["start_page"]
                se = subsection["end_page"]

                if ss <= number <= se:
                    relevant_subsections.append({
                        "id": subsection["subsection_id"],
                        "type": "subsection",
                        "heading": subsection["heading"],
                        "text": subsection["text"],
                        "pages": list(range(ss, se + 1)),
                    })

            if relevant_subsections:
                node["subsections"] = relevant_subsections

            page_index[number]["nodes"].append(node)

    return {
        "document": {
            "total_pages": len(document.get("pages", [])),
        },
        "pages": list(page_index.values()),
    }


def save_page_index(page_index, output_path):
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    with open(output_path, "w", encoding="utf-8") as file:
        json.dump(
            page_index,
            file,
            indent=2,
            ensure_ascii=False,
        )
