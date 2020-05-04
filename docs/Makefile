# Minimal makefile for Sphinx documentation
#

# You can set these variables from the command line, and also
# from the environment for the first two.
SPHINXOPTS        ?= -D language='en' -A GAID='xxx' -A VERSION='refs/heads/master'
TX                ?= tx
SPHINXBUILD       ?= sphinx-build
SPHINXINTL        ?= sphinx-intl
SPHINXAUTOBUILD   ?= sphinx-autobuild
SOURCEDIR         = .
BUILDDIR          = _build
LOC               ?=
PROJECT           ?=

# Put it first so that "make" without argument is like "make help".
help:
	@echo "  serve       to run development server with auto-reload"
	@echo "  update      to prepate .pot files for PROJECT"
	@echo "  push        to push .pot files to Transifex"
	@echo "  pull        to pull .po files from Transifex for LOC or all"
	@$(SPHINXBUILD) -M help "$(SOURCEDIR)" "$(BUILDDIR)" $(SPHINXOPTS) $(O)

serve:
	@$(SPHINXAUTOBUILD) "$(SOURCEDIR)" "$(BUILDDIR)/html" $(SPHINXOPTS)

update:
	@$(SPHINXBUILD) -M gettext "$(SOURCEDIR)" "$(BUILDDIR)" $(SPHINXOPTS)
	@$(SPHINXINTL) update-txconfig-resources --pot-dir "$(BUILDDIR)/gettext" --transifex-project-name "$(PROJECT)"

push:
	@$(TX) push -s

pull:
ifeq ($(LOC),)
	@$(TX) pull
else
	@$(TX) pull -l "$(LOC)"
endif

clean:
	rm -r _build
	rm -r reference/api

.PHONY: help serve update push pull clean Makefile

# Catch-all target: route all unknown targets to Sphinx using the new
# "make mode" option.  $(O) is meant as a shortcut for $(SPHINXOPTS).
%: Makefile
	@$(SPHINXBUILD) -M $@ "$(SOURCEDIR)" "$(BUILDDIR)" $(SPHINXOPTS) $(O)
