# freeipa-manager
[![Build Status](https://travis-ci.org/gooddata/freeipa-manager.svg?branch=master)](https://travis-ci.org/gooddata/freeipa-manager)
## Overview
*freeipa-manager* is a tool for management of [FreeIPA](https://github.com/freeipa/freeipa)
entities. It makes it easier to setup and maintain identity management using FreeIPA
by keeping the configuration of users, groups, rules and other entities in files
that can be easily version-controlled.

## Motivation
The main purpose of the tool is to enable a FreeIPA administrator to
**keep FreeIPA entity configuration in a VCS**. This means that the definition
of FreeIPA users, groups, rules, and other entities can be committed to, for
instance, a Git repo, which enables one to:
* backup and restore entities easily,
* easily transfer entity structure from one FreeIPA domain to another,
* enforce entity configuration from a version-controlled and reviewed state,
* keep track of entity changes made via FreeIPA UI in a repository,
* define (and enforce) a meta-structure over entities.

The ultimate goal of the tool is the ability to implement the **role-based access
control** (RBAC) philosophy, which would be tedious and impractical without a clean
control over entities that version control grants us.

## Usage
The following examples assume that the configuration directory (as described
below in the *Configuration* section) is located in a path called *config*.
### check
```
ipamanager check config
```
The most basic only verifies that the entities defined in the config follow
the pre-defined structure/integrity rules.

Integrity check verifies basic consistency of entities, such as:
* whether entities are only members of existing entities,
* whether entities are only members of entities of allowed types,
* that there are no cycles in the membership,
* that HBAC/sudo rules have a member hostgroup & user group.


The integrity check module also supports additional settings and constraints
on the entity structure, such as:
* that users can only be (direct) members of groups with given naming convention
  (e.g., a group must be named '\*-users' to be able to contain users directly),
* that nesting of group membership can only go up to a certain level
  (e.g., max. group1 -> group2 -> group3 - maximum nesting level 2),
* ...

### push
```
ipamanager push config
```
The `push` command, after verifying the entities (like `check`), configures
the defined entities on the FreeIPA server.

The default mode of this command is a *dry run*, overriden by the `--force` flag.

The address of the FreeIPA server is parsed by the `ipalib` package from the
`/etc/ipa/default.conf` config file.

### pull
```
ipamanager pull config
```
Analogically to `push`, the `pull` command dumps the current state of entities
on a FreeIPA server to files in the config directory.

Additionally, using the `ipamanager-pull-request` command from the included
`ipamanager.tools` package, a GitHub pull request can be opened against the config
repository with the dumped changes.

### diff
```
ipamanager diff folder1 folder2
```
The `diff` command is useful for listing entities that are extra in `folder1`
compared to `folder2`, e.g.:
* listing users defined for one domain but not for another (see *Multiple domains*
  below for details), or
* listing HBAC rules with no corresponding sudo rule with the same name.

### template
```
ipamanager template template.yaml config
```
The `template` command creates all the entities for a subcluster defined in the 
`template.yaml` to the `repo` locally. Entities needs to be reviewed and then commited
to the config repository manually.

Example of the `template.yaml` file with decsription can be found in [tests/example_template.yaml](tests/example_template.yaml)

### roundtrip
```
ipamanager roundtrip config
```
The `roundtrip` command can be used to load entities from config files
(like the `check` command, but without integrity checking), then store
them right back to the configuration files.

This can be useful when your config is technically correct, but there are
style issues in it (e.g., the `memberOf` lists values are unsorted).
Round-trip will fix these issues. Alternatively, a `pull` operation would
fix such issues in the config of entities changed on the FreeIPA server as well,
but such a commit would contain both server-side changes and style fixes;
this could lead to a confusing diff, which may be undesirable.

### Dry run
The *dry run* mode can be choosen with `-d` or `--dry-run` flag.

## Configuration
The most practical way of keeping configuration for the tool is to dedicate
a separate repository for the purpose.

### Directory structure
#### Single domain
Inside the repository, there should be
a subfolder per each entity type, like this:
```
groups/
hbacrules/
hbacsvcgroups/
hbacsvcs/
hostgroups/
permissions/
privileges/
roles/
services/
sudorules/
users/
```

#### Multiple domains
Alternatively, it is possible to keep configuration for several FreeIPA domains
in a single repository, by dividing it into per-domain subfolders, e.g.:
```
domain1/
  groups/
  hbacrules/
  hostgroups/
domain2/
  hostgroups/
  users/
  groups/
...
```

#### Unmanaged types
Entity types you don't wish to manage using *freeipa-manager* do not need to have
their own folders in the structure; however, **please note they may be deleted**
by the `push` command run unless you specify the ignore settings correctly (see
the *Settings file#Ignored entities* stanza below for details).

### Entity definition
The entity configuration is kept in files of the **YAML** format.

There should be a separate configuration file for each entity. The entity should
be defined as a mapping, where the only top-level key is the entity's `id` in FreeIPA
while the nested keys are the particular values of its parameters.

#### Membership definition
FreeIPA permits several relationships between entities to be defined, such as:
* users can be members of user groups,
* hosts can be members of host groups,
* HBAC & sudo rules have users, hosts & groups as members,
* ...

In *freeipa-manager*, these relationships are captured by two ways:
1. The **memberOf** attribute. This is useful where we want to model the relationships
on the side of the *member*, e.g., for users (where *memberOf* contains a list of
a given user's groups) or groups (what other group a given group is a member of).
2. The **member(Host|User)** attribute. This is used wherever we want to capture the
membership relation of entities on the side of the *target* entity. Currently, this
is used for HBAC rules & sudo rules.

See the per-type entity config descriptions below for more details.

#### Meta parameters
In addition to the FreeIPA-mandated entity structure, a special parameter, called
**metaparams**, can be defined for *any* entity type. This key can contain an arbitrary
mapping of keys and values, for instance:
```yaml
entity1:
  ...
  metaparams:
    metakey1: value1
    key2:
      subkey: subvalue
      another: [value, value2]
```
The value of this key is ignored by the tool (and preserved even with the `pull`
command).

Meta parameters can be useful for defining a separate data structure on top of the
FreeIPA entities; for example, you could have a key called `approval` inside
`metaparams` for user groups and check whether an approval is needed for an user
to be added to a given group (e.g., as part of pull request testing). While you
would currently need to write a separate tooling for that, native support for
meta parameter processing is planned in *freeipa-manager* as well.

### Type-specific config
Each entity type has its own set of parameters that FreeIPA supports. The structure
that the tool expects for an entity configuration is defined in the `ipamanager/schemas.py`
module and parsed by the `voluptuous` package.

#### Users
The user entity type is the most parametrized one; a maximum record can look like the following:
```yaml
user.name:
  firstName: Test  # required
  lastName: User  # required
  initials: TU
  emailAddress: testuser@example.com  # can also be a list of addresses
  organizationUnit: Department1
  manager: some.manager  # ID of another existing user
  githubLogin: abclogin1  # maps to the 'carlicense' attribute
  title: SW Engineer
  memberOf:
    group: [group1, other-group]
  metaparams:
    param1: value1
    param2: value2
```
A user can be a member of any number of user groups. However, the default
membership in the `ipausers` group is not captured in the config; it is added
automatically to each user entity by the tool itself.

#### User groups
The user group entity is much simpler; a minimal example could look like this:
```yaml
group1:
```
A maximum example:
```yaml
group1:
  description: A sample group.
  posix: False
  memberOf:
    group:
      - group2
  metaparams: ...
```
User groups can be members of other user groups.

Note that the user group type is just called `group`, not `usergroup`, since that
is the way that FreeIPA references the type as well (e.g., in the `ipa group-add`
command).

#### Host groups
Host groups are analogical to user groups, minus the POSIX option:
```yaml
group1:
  description: A sample group.
  posix: False
  memberOf:
    hostgroup:
      - group2
  metaparams: ...
```

#### HBAC rules
HBAC rules define a mapping of access between user groups and host groups.

```yaml
rule1:
  description: An example HBAC rule.
  memberHost: [hostgroup1, hostgroup2]
  memberUser: [usergroup1, usergroup2]
  memberService: httpd  # mutually exclusive with serviceCategory
  serviceCategory: all  # mutually exclusive with memberService
```
**NOTE:** FreeIPA allows defining users and hosts as direct members of HBAC rules;
however, since our use cases always required a structure where only groups are
allowed to be members of rules, we decided to disregard such a possibility in
the configuration.

Additionally, our config requires HBAC rules to have at least one `memberHost`
and at least one `memberUser`.

#### Sudo rules
Sudo rules are similar to HBAC rules in terms of `memberHost`/`memberUser`, but
they have some specific options:
```yaml
rule1:
  description: An example HBAC rule.
  memberHost: [hostgroup1, hostgroup2]
  memberUser: [usergroup1, usergroup2]
  cmdCategory: all
  options:  # maps to the ipasudoopt attribute
    - !authenticate
  runAsGroupCategory: all
  runAsUserCategory: all
```
**NOTE:** FreeIPA allows defining users and hosts as direct members of sudo rules;
however, since our use cases always required a structure where only groups are
allowed to be members of rules, we decided to disregard such a possibility in
the configuration.

Additionally, our config requires HBAC rules to have at least one `memberHost`
and at least one `memberUser`.

#### HBAC services (`hbacsvcs`)
```yaml
service1:
  description: A sample service managed by HBAC rules.
  memberOf:
    hbacsvcgroups:
      - servicegroup1
      - servicegroup2
```
Since FreeIPA defines quite a comprehensive set of HBAC services (such as `sshd`
or `httpd`) by default, one may not ever need to define additional entities of type
type, but it's nevertheless possible.

#### HBAC service groups (`hbacsvcgroups`)
```yaml
servicegroup1:
  description: A group of HBAC services.
  metaparams:
    param1: [value1, value1.1]
```

#### Roles
Roles are usually used to define access to functionalities inside FreeIPA itself.
They can be members of `privilege` entities:
```yaml
role-one:
  description: A role.
  memberOf:
    privilege: [privilege1]
```

#### Privileges
Privileges serve as "middleware" between `roles` and `permissions`:
```yaml
sample-privilege:
  description: A sample privilege entity.
  memberOf:
    permission:
      - 'System: Add Groups'
      - another-permission
```

#### Permissions
Permissions are the final level of access definition inside FreeIPA; they can
allow access to specific FreeIPA functions by granting read/write access to the
relevant parts of the underlying LDAP tree structure.

There are pre-defined "System:" permissions, and you can also define your own:
```yaml
new-permission:
  description: A permission to do something in FreeIPA.
  subtree: subtree-name
  attributes:
    - firstName
    - lastName
    - initials
  grantedRights: [read, write]  # can also be just a string
  defaultAttr: initials
  location: cn=users,cn=accounts,dc=example,dc=com
```

#### Services
Services are the per-host principals that allow getting keytabs & certificates.
```yaml
HTTP/host1.example.com:
  managedBy: [host1.example.com]  # can also be just a string
  description: A sample HTTP service for host1.example.com.
  metaparams:
    param1: value2
```
If hosts in your domain change often, you might find it impractical to manage
services via this tool; however, it might be useful if your hosts are largely static.

### Settings file
In addition to definitions of entities themselves, a *settings* file is needed
to provide additional configuration of the tool itself.

Like entity config files, the settings file uses the YAML format.
Currently, the following settings are supported:
#### ignore
Defines a list of regexes for each entity type; if a name of an entity of the
given type matches any of the relevant expressions, it will not be noticed by
the tool, whether encountered in the config files or on FreeIPA server.

This key is optional, and it does not have to contain every entity type;
by default, no entity is ignored.
```yaml
# example
ignore:
  user: [admin, test.+]
  service: [.*]
```
#### user-group-pattern
Defines a pattern that user group entities' names must match for them to be allowed
to contain users directly. This is useful when defining a strict, nested group structure.

If this key's value is set to an empty string (`''`), this is not enforced and any
user group can contain users directly.

#### nesting-limit
Defines maximum nesting level of group membership. E.g., a level of 3 means that
entities can be nested at most like this:
```yaml
group1 -> group2 -> group3 -> group4
```
This should be a number. If this is not provided, nesting limit is not enforced.

#### alerting
Defines configuration for alerting plugins that should send a result of the tool's
run to a monitoring service. Several plugins can be configured:
```yaml
# example
alerting:
  test-monitoring:
    module: test_monitoring
    class: TestMonitoringPlugin
    config:
      key1: value1
      key2: value2
  other-alerting:
    module: other.test
    class: OtherAlertingPlugin
```
This would instantiate the plugins `alerting.test_monitoring.TestMonitoringPlugin`
and `alerting.other.testOtherAlertingPlugin`. The `config` dictionary value is
passed to the plugin instance without modification.


## Further development
Several new features of *freeipa-manager* are planned for the future, such as:
### Meta parameter processing support
It should be possible to define a structure of *labels* in *metaparams* for users
that will define roles (in accordance with RBAC) necessary for membership in certain
groups. The tool should process these labels and ensure that group membership is
only granted if all the defined criteria are met.
### Distribute a Linux manpage and autocompletion
Since *freeipa-manager* is a tool for Linux environment, distributing a manual entry
with it would be reasonable, since it's the standard for Linux tools.
Similarly, `Tab` key auto-completion of commands is a standard and would be useful.
### Support for pure LDAP
The tool could possibly interface LDAP directly instead of the higher-level FreeIPA
API. This would enable a wider range of applications.
