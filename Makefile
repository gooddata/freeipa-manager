# @help FreeIPA entity management tooling
#
# A documentation of Makefile targets follows.
help:
	@perl -M5.010 -ne 'BEGIN{undef $$/} while(/^# \@help( .*\s*)((?:^#.*\s*)*)^(\S+):/gm){\
	say "$$3:"; my $$x = $$1 . $$2; $$x =~ s/^#? ?/   /gm; say $$x }' Makefile | fmt


VIRTUALENV ?= virtualenv
VENV_DIR = .venv
VENV_ACTIVATE = $(VENV_DIR)/bin/activate
VENV_CMD = . $(VENV_ACTIVATE);
REQUIREMENTS_FILE = requirements.txt
REQUIREMENTS = $(VENV_DIR)/requirements.installed

CONFIG_REPO ?= ../../freeipa-manager-config/entities
CHECK_CMD = src/freeipa_manager.py $(CONFIG_REPO) -t $(ENTITY_TYPES)


# @help parse & validate configuration
check: $(REQUIREMENTS) check-yaml
	$(VENV_CMD) $(CHECK_CMD) $(if $(DEBUG), '-d')

# @help check YAML config files for syntax errors
check-yaml: $(REQUIREMENTS)
	$(VENV_CMD) yamllint -f parsable $(CONFIG_REPO)

$(VENV_ACTIVATE):
	$(VIRTUALENV) $(VENV_DIR)

$(REQUIREMENTS): $(VENV_ACTIVATE) $(REQUIREMENTS_FILE)
	$(VENV_CMD) pip install -r $(REQUIREMENTS_FILE)
	touch $@

clean:
	rm -rf $(VENV_DIR)
