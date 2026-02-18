.PHONY: vendor build clean serve tidy tags

# https://cdnjs.com/libraries/mermaid
VERSION ?= 11.12.0
MERMAID_URL = https://cdnjs.cloudflare.com/ajax/libs/mermaid/$(VERSION)/mermaid.min.js
VENDOR = site/static/js/mermaid.min.js

vendor:
	@mkdir -p $(dir $(VENDOR))
	@curl -fsSL "$(MERMAID_URL)" -o "$(VENDOR)"
	@echo "Vendored mermaid $(VERSION) -> $(VENDOR)"

build:
	hugo -s site --minify --cleanDestinationDir

clean:
	rm -rf site/public

serve:
	hugo server -D -s site

tidy:
	python3 scripts/normalize_content.py
	python3 scripts/add_summary_description.py
	python3 scripts/update_internal_links.py
	python3 scripts/sort_tags.py

tags:
	python3 scripts/tag_frequency.py --top 40
