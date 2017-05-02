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
LDAP_SERVER ?= $(shell ./ldap_server.sh)
DIFF_TARGET ?= .diff

BASE_CMD = src/freeipa_manager.py
CMD_SUFFIX = -t $(ENTITY_TYPES) $(if $(DEBUG), '-v')
ARG_CONF = $(if $(CONFIG_REPO), --conf $(CONFIG_REPO))
ARG_REMOTE = $(if $(LDAP_SERVER), --remote $(LDAP_SERVER))


# @help check YAML config files for syntax errors
check-yaml: $(REQUIREMENTS)
	$(VENV_CMD) yamllint -f parsable $(CONFIG_REPO)

# @help parse & validate configuration from repository & LDAP server
check: $(REQUIREMENTS) check-yaml
	$(VENV_CMD) $(BASE_CMD) check $(ARG_CONF) $(ARG_REMOTE) $(CMD_SUFFIX)

# @help parse & validate configuration from repository only
check-config: $(REQUIREMENTS) check-yaml
	$(VENV_CMD) $(BASE_CMD) check $(ARG_CONF) $(CMD_SUFFIX)

# @help parse & validate configuration from LDAP server only
check-ldap: $(REQUIREMENTS)
	$(VENV_CMD) $(BASE_CMD) check $(ARG_REMOTE) $(CMD_SUFFIX)

# @help compare configuration in repository vs. LDAP server
compare: $(REQUIREMENTS) check-yaml
	$(VENV_CMD) $(BASE_CMD) compare $(ARG_CONF) $(ARG_REMOTE) $(CMD_SUFFIX) > $(DIFF_TARGET)

# @help pull configuration from LDAP server into config repository
pull: $(REQUIREMENTS)
	$(VENV_CMD) $(BASE_CMD) pull $(ARG_CONF) $(ARG_REMOTE) $(CMD_SUFFIX)

# @help push configuration from config repository to LDAP server (add-only)
push: $(REQUIREMENTS) check-yaml
	$(VENV_CMD) $(BASE_CMD) push $(ARG_CONF) $(ARG_REMOTE) $(CMD_SUFFIX)


$(VENV_ACTIVATE):
	$(VIRTUALENV) $(VENV_DIR)

$(REQUIREMENTS): $(VENV_ACTIVATE) $(REQUIREMENTS_FILE)
	$(VENV_CMD) pip install -r $(REQUIREMENTS_FILE)
	touch $@

clean:
	rm -rf $(VENV_DIR)
