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
DIFF_TARGET ?= .diff

BASE_CMD = src/freeipa_manager.py $(CONFIG_REPO) 
CMD_SUFFIX = -t $(ENTITY_TYPES) $(if $(DEBUG), '-v') 


# @help check YAML config files for syntax errors
check-yaml: $(REQUIREMENTS)
	$(VENV_CMD) yamllint -f parsable $(CONFIG_REPO)

# @help parse & validate configuration from repository & LDAP server
check: $(REQUIREMENTS) check-yaml
	$(VENV_CMD) $(BASE_CMD) check $(ARG_CONF) -d $(DOMAIN) $(CMD_SUFFIX)

# @help parse & validate configuration from repository & localhost LDAP
check-local: $(REQUIREMENTS) check-yaml
	$(VENV_CMD) $(BASE_CMD) check $(ARG_CONF) -d localhost $(CMD_SUFFIX)

# @help parse & validate configuration from repository only
check-config: $(REQUIREMENTS) check-yaml
	$(VENV_CMD) $(BASE_CMD) check $(CMD_SUFFIX)

# @help compare configuration in repository vs. LDAP server
compare: $(REQUIREMENTS) check-yaml
	$(VENV_CMD) $(BASE_CMD) compare $(CMD_SUFFIX) -d $(DOMAIN) > $(DIFF_TARGET)

# @help compare configuration in repository vs. localhost LDAP server
compare-local: $(REQUIREMENTS) check-yaml
	$(VENV_CMD) $(BASE_CMD) compare $(CMD_SUFFIX) -d localhost > $(DIFF_TARGET)

# @help pull configuration from LDAP server into config repository
pull: $(REQUIREMENTS)
	$(VENV_CMD) $(BASE_CMD) pull -d $(DOMAIN) $(CMD_SUFFIX)

# @help pull configuration from LDAP server into config repository
pull-local: $(REQUIREMENTS)
	$(VENV_CMD) $(BASE_CMD) pull -d localhost $(CMD_SUFFIX)

# @help push configuration from config repository to LDAP server (add-only)
push: $(REQUIREMENTS) check-yaml
	$(VENV_CMD) $(BASE_CMD) push -d $(DOMAIN) $(CMD_SUFFIX)

# @help push configuration from config repository to LDAP server (add-only)
push-local: $(REQUIREMENTS) check-yaml
	$(VENV_CMD) $(BASE_CMD) push -d localhost $(CMD_SUFFIX)


$(VENV_ACTIVATE):
	$(VIRTUALENV) $(VENV_DIR)

$(REQUIREMENTS): $(VENV_ACTIVATE) $(REQUIREMENTS_FILE)
	$(VENV_CMD) pip install -r $(REQUIREMENTS_FILE)
	touch $@

clean:
	rm -rf $(VENV_DIR)
