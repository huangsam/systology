.PHONY: vendor vendor-mermaid vendor-katex build build-force clean serve tidy tags insights check check-sync

# https://www.jsdelivr.com/package/npm/mermaid
MERMAID_VERSION ?= 11.16.0
MERMAID_URL = https://cdn.jsdelivr.net/npm/mermaid@$(MERMAID_VERSION)/dist/mermaid.min.js
MERMAID_VENDOR = site/assets/js/mermaid.min.js

# https://www.jsdelivr.com/package/npm/katex
KATEX_VERSION ?= 0.16.21
KATEX_URL = https://registry.npmjs.org/katex/-/katex-$(KATEX_VERSION).tgz
KATEX_VENDOR_DIR = site/static/vendor/katex

vendor: vendor-mermaid vendor-katex

vendor-mermaid:
	@mkdir -p $(dir $(MERMAID_VENDOR))
	@curl -fsSL "$(MERMAID_URL)" -o "$(MERMAID_VENDOR)"
	@echo "Vendored mermaid $(MERMAID_VERSION) -> $(MERMAID_VENDOR)"

vendor-katex:
	@mkdir -p $(KATEX_VENDOR_DIR)
	@curl -fsSL "$(KATEX_URL)" | tar -xzf - --strip-components=2 -C "$(KATEX_VENDOR_DIR)" package/dist
	@echo "Vendored katex $(KATEX_VERSION) -> $(KATEX_VENDOR_DIR)"

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
