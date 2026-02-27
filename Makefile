.PHONY: vendor index build clean serve tidy tags

# https://cdnjs.com/libraries/mermaid
VERSION ?= 11.12.0
MERMAID_URL = https://cdnjs.cloudflare.com/ajax/libs/mermaid/$(VERSION)/mermaid.min.js
VENDOR = site/static/js/mermaid.min.js

vendor:
	@mkdir -p $(dir $(VENDOR))
	@curl -fsSL "$(MERMAID_URL)" -o "$(VENDOR)"
	@echo "Vendored mermaid $(VERSION) -> $(VENDOR)"

index:
	python3 manage.py index

build: index
	hugo -s site --minify --cleanDestinationDir

clean:
	rm -rf site/public

serve: index
	hugo server -D -s site --baseURL=http://localhost:1313/

tidy:
	python3 manage.py tidy

check:
	python3 manage.py check

tags:
	python3 manage.py stats --top 40
