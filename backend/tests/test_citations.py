from app.services.citations import keep_cited


def test_only_cited_passages_are_kept_and_renumbered():
    text, cited = keep_cited("Use PgBouncer [3]. Cap the pool [3][5].", passage_count=5)
    assert cited == [3, 5]
    assert text == "Use PgBouncer [1]. Cap the pool [1][2]."


def test_comma_lists_are_expanded():
    text, cited = keep_cited("Both agree [2, 1].", passage_count=3)
    assert cited == [2, 1]
    assert text == "Both agree [1][2]."


def test_no_citations_means_no_sources():
    text, cited = keep_cited("I couldn't find that in your saved items.", passage_count=5)
    assert cited == []
    assert text == "I couldn't find that in your saved items."


def test_bracketed_numbers_that_are_not_passages_are_untouched():
    text, cited = keep_cited("Released in [2024], see [1].", passage_count=2)
    assert cited == [1]
    assert text == "Released in [2024], see [1]."
