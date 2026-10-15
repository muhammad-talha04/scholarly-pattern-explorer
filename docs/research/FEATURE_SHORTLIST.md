# Feature shortlist

Free literature tools students already use, and features we can add from
OpenAlex on its free tier. Left out on purpose, because they are already
being built: gap finder, papers-like-this, emerging topics, compare view,
collections, related-papers map, and the first-run tour. Release 2 already
covers the citation map, topic and author alerts, collections, side-by-side
comparison, and influential citations, so those are not listed again.

Limits below are the public free tiers as described in 2026. Vendors change
them. OpenAlex itself is CC0. Paginated or bulk access beyond the first page
requires a free API key (repo secret `OPENALEX_API_KEY`, already set). Every
feature listed below stays on that free tier.

## What the free tools do

| Tool | Free tier | What a student actually uses | Where the data comes from |
|---|---|---|---|
| Semantic Scholar | Search and API are free | Keyword search, TLDR lines, related papers, citation lists, influential-citation marks, author pages | Their own corpus. The API is free and rate-limited |
| Connected Papers | About 5 graphs a month | One seed paper drawn as a similarity graph, including papers that do not cite each other | Semantic Scholar |
| ResearchRabbit | Free collections, with a seed cap around 50; a paid tier raises it | A saved set of papers that recommends more, plus citation and co-author graphs | Their index (Semantic Scholar and PubMed) |
| Elicit | Basic is free: unlimited search and summaries, limited Research Agent use. The systematic-review workflow is paid | A question in, papers and short summaries out; paid plans add column extraction and screening | Elicit's own corpus (about 138 million papers), not OpenAlex |
| Litmaps | About 2 maps and 100 articles on the free plan | A timeline of papers (year against citations) and alerts for new papers | Their own index |
| Inciteful | Free, no account | Ranks for similar and important papers, top authors, and a Literature Connector between two papers | OpenAlex, Semantic Scholar, Crossref, OpenCitations |

We already cover meaning search, summaries, ask-about-a-paper, country counts,
incremental topic patterns, the gap finder, and related papers. The gaps below
are the ones those tools have that we do not.

## Features we can build on OpenAlex

Effort is the size of the change, not a calendar estimate.

- **Small** — one filter or one field on a page we already have.
- **Medium** — a new route that aggregates authors or walks citation ids.
- **Large** — a new pass over abstracts.

| Feature | What the student gets | Effort | OpenAlex data |
|---|---|---|---|
| Open-access filter and a direct PDF link | Keep only papers with a free full text, and open it | Small | `open_access.is_oa`, `open_access.oa_url` |
| Retraction flag | A warning on a paper Retraction Watch has retracted | Small | `is_retracted` |
| Topic, language, and type facets | Narrow a search by field, subfield, language, or article vs preprint | Small | `primary_topic` (field, subfield, display name), `language`, `type` |
| BibTeX export of the current results | Download the papers on screen as BibTeX | Small | `display_name`, `authorships`, `publication_year`, `biblio`, `doi` |
| Most-cited papers for a topic | A citation sort beside the meaning sort, so foundational papers surface | Small | `cited_by_count`, `primary_topic` |
| Citation timeline for a search | Year against citation count for the papers a query returned (the Litmaps view) | Small | `publication_year`, `cited_by_count` |
| Literature connector | The citation path between two papers the student names | Medium | `referenced_works`, and the `cites` filter for the other direction |
| Authors and institutions for a topic | Who publishes this topic, and where, ranked by paper count | Medium | `authorships.author`, `authorships.institutions` |
| Funders for a topic | Which funders pay for this topic | Medium | `funders`, `awards` (OpenAlex replaced the old `grants` field with these) |
| Abstract evidence table | Columns for method, data, and result, filled from abstracts across a result list | Large | `abstract_inverted_index` (or the abstract text we already store). Use the extractive summariser in `ml/text.py`; a paid LLM is optional |
