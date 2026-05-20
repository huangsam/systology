.PHONY: vendor build build-force clean serve tidy tags insights check

# https://cdnjs.com/libraries/mermaid
VERSION ?= 11.12.0
MERMAID_URL = https://cdnjs.cloudflare.com/ajax/libs/mermaid/$(VERSION)/mermaid.min.js
VENDOR = site/assets/js/mermaid.min.js

vendor:
	@mkdir -p $(dir $(VENDOR))
	@curl -fsSL "$(MERMAID_URL)" -o "$(VENDOR)"
	@echo "Vendored mermaid $(VERSION) -> $(VENDOR)"

build:
	@if [ -z "$(FORCE)" ] && lsof -i :1313 >/dev/null 2>&1; then \
		echo "Error: Dev server is running on :1313. Use FORCE=1 or stop server to build."; \
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

tags:
	python3 manage.py stats --top 40

insights:
	python3 manage.py insights
