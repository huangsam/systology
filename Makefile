.PHONY: vendor build build-force clean serve tidy tags insights check check-sync

# https://www.jsdelivr.com/package/npm/mermaid
VERSION ?= 11.16.0
MERMAID_URL = https://cdn.jsdelivr.net/npm/mermaid@$(VERSION)/dist/mermaid.min.js
VENDOR = site/assets/js/mermaid.min.js

vendor:
	@mkdir -p $(dir $(VENDOR))
	@curl -fsSL "$(MERMAID_URL)" -o "$(VENDOR)"
	@echo "Vendored mermaid $(VERSION) -> $(VENDOR)"

build:
	@if lsof -i :1313 >/dev/null 2>&1; then \
		echo "Error: Dev server is running on :1313. Stop the server to build."; \
		exit 1; \
	fi
	hugo -s site --minify --cleanDestinationDir

build-force:
	hugo -s site --minify --cleanDestinationDir

clean:
	rm -rf site/public

serve:
	hugo server -D -s site --baseURL=http://localhost:1313/systology/ --disableFastRender

tidy:
	python3 manage.py tidy

check:
	python3 manage.py check

check-sync:
	python3 manage.py check-sync

tags:
	python3 manage.py stats --top 40

insights:
	python3 manage.py insights
