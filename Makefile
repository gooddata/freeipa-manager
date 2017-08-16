# @help FreeIPA entity management tooling
#
# A documentation of Makefile targets follows.
help:
	@perl -M5.010 -ne 'BEGIN{undef $$/} while(/^# \@help( .*\s*)((?:^#.*\s*)*)^(\S+):/gm){\
	say "$$3:"; my $$x = $$1 . $$2; $$x =~ s/^#? ?/   /gm; say $$x }' Makefile | fmt


VIRTUALENV ?= virtualenv --system-site-packages
VENV_DIR = .venv
VENV_ACTIVATE = $(VENV_DIR)/bin/activate
VENV_CMD = . $(VENV_ACTIVATE);
REQUIREMENTS_FILE = requirements.txt
REQUIREMENTS = $(VENV_DIR)/requirements.installed

CONFIG_REPO ?= ../../freeipa-manager-config/entities
RULES_FILE ?= ../../freeipa-manager-config/integrity_config.yaml
THRESHOLD ?= 20

BASE_CMD = src/freeipa_manager.py $(CONFIG_REPO) 
CMD_SUFFIX = -r $(RULES_FILE) -t $(THRESHOLD) $(if $(IGNORED), -i $(IGNORED)) $(if $(DEBUG), '-v')


# @help check YAML config files for syntax errors
check-yaml: $(REQUIREMENTS)
	$(VENV_CMD) yamllint -f parsable $(CONFIG_REPO)

# @help parse & validate configuration from local config repo
check: $(REQUIREMENTS) check-yaml
	$(VENV_CMD) $(BASE_CMD) check $(CMD_SUFFIX)

# @help compare configuration between local repo & FreeIPA server
compare: $(REQUIREMENTS) check-yaml
	$(VENV_CMD) $(BASE_CMD) push $(CMD_SUFFIX)

# @help compare configuration between local repo & FreeIPA server (including extra remote entity deletion)
compare-enable-del: $(REQUIREMENTS) check-yaml
	$(VENV_CMD) $(BASE_CMD) push --enable-deletion $(CMD_SUFFIX)

# @help push configuration from config repository to FreeIPA server
push: $(REQUIREMENTS) check-yaml
	$(VENV_CMD) $(BASE_CMD) push --force $(CMD_SUFFIX)

# @help push configuration from config repository to FreeIPA server (including extra remote entity deletion)
push-enable-del: $(REQUIREMENTS) check-yaml
	$(VENV_CMD) $(BASE_CMD) push --force --enable-deletion $(CMD_SUFFIX)

# @help pull configuration from FreeIPA server into config repository
pull: $(REQUIREMENTS)
	$(VENV_CMD) $(BASE_CMD) pull $(CMD_SUFFIX)

$(VENV_ACTIVATE):
	$(VIRTUALENV) $(VENV_DIR)

$(REQUIREMENTS): $(VENV_ACTIVATE) $(REQUIREMENTS_FILE)
	$(VENV_CMD) pip install -r $(REQUIREMENTS_FILE)
	touch $@

clean:
	rm -rf $(VENV_DIR)
