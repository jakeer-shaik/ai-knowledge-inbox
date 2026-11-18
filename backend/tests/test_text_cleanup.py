from app.services.text_cleanup import clean_extracted_text

ARTICLE = "Vector databases store embeddings.[1][2] They use ANN search.[citation needed]\n\n" + "Body text. " * 40


def test_footnote_markers_are_removed_so_they_cant_clash_with_citations():
    cleaned = clean_extracted_text(ARTICLE)
    assert "[1]" not in cleaned and "[2]" not in cleaned and "[citation needed]" not in cleaned
    assert cleaned.startswith("Vector databases store embeddings. They use ANN search.")


def test_edit_links_and_heading_anchors_are_removed():
    cleaned = clean_extracted_text("History\n[edit]\nBackground Tasks¶\nText.")
    assert cleaned == "History\n\nBackground Tasks\nText."


def test_reference_section_at_the_end_is_dropped():
    text = ARTICLE + "\nReferences\n- ↑ Smith (2023). \"Paper\". Retrieved 2024-01-01.\n- ↑ Doe (2022)."
    cleaned = clean_extracted_text(text)
    assert "References" not in cleaned and "Retrieved" not in cleaned
    assert cleaned.endswith("Body text.")


def test_reference_list_longer_than_the_article_is_still_dropped():
    refs = "\n".join(f'- 1 2 "Source {i}". example.com. Retrieved 2024-01-0{i % 9}.' for i in range(40))
    cleaned = clean_extracted_text("Short article. " * 20 + "\nReferences\n" + refs)
    assert "References" not in cleaned and "Retrieved" not in cleaned
    assert cleaned.startswith("Short article.")


def test_early_see_also_heading_does_not_truncate_the_article():
    text = "See also\nIntro line.\n" + ARTICLE
    assert "Body text." in clean_extracted_text(text)


def test_table_rules_are_dropped_but_rows_kept():
    cleaned = clean_extracted_text("| Name | Kind |\n|---|---|\n| Milvus | open source |")
    assert cleaned == "| Name | Kind |\n| Milvus | open source |"


def test_code_is_kept():
    code = "from fastapi import BackgroundTasks\napp = FastAPI()"
    assert clean_extracted_text(code) == code
