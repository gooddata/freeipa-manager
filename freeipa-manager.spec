Name:           freeipa-manager
Version:        1.10
Release:        1%{?dist}
Summary:        FreeIPA entity provisioning tool

License:        BSD License 2.0
URL:            https://github.com/gooddata/freeipa-manager
Source0:        %{name}.tar.gz

Requires:       python
Requires:       gdc-python-common
Requires:       PyYAML >= 3.10
Requires:       python-argcomplete
Requires:       python-requests >= 2.6.0
Requires:       python-sh >= 1.11
Requires:       python-voluptuous >= 0.8.5
Requires:       python2-yamllint >= 1.8.1
Requires:       /usr/sbin/send_nsca
BuildRequires:  pytest python-argcomplete python-psutil python-setuptools
Conflicts:      gdc-ipa-utils < 6

%description
FreeIPA entity provisioning and management tooling.

%prep
%setup -q -c -n %{name}

%build
%define debug_package %{nil}

export PACKAGE_VERSION=%{version}.%{release}
%{__python} setup.py build

%install
rm -rf $RPM_BUILD_ROOT
mkdir -p $RPM_BUILD_ROOT

export PACKAGE_VERSION=%{version}.%{release}
%{__python} setup.py install -O1 --skip-build --root $RPM_BUILD_ROOT

# install autocompletion script
mkdir -p $RPM_BUILD_ROOT/etc/bash_completion.d
register-python-argcomplete ipamanager > $RPM_BUILD_ROOT/etc/bash_completion.d/ipamanager

%files
%defattr(-,root,root,-)
%{python_sitelib}/freeipa_manager*
%{python_sitelib}/ipamanager*
%{_bindir}/ipamanager
%{_bindir}/ipamanager-pull-request
%{_bindir}/ipamanager-query
/etc/bash_completion.d/ipamanager

%changelog
* Mon May 25 2020 Kristian Lesko <kristian.lesko@gooddata.com> - 1.9-1
- Support filter parameters in permission entity
* Tue Sep 10 2019 Kristian Lesko <kristian.lesko@gooddata.com> - 1.8-3
- Add Bash command autocompletion
* Fri Sep 06 2019 Kristian Lesko <kristian.lesko@gooddata.com> - 1.8-2
- Fix change threshold calculation (cap values to 100 %)
* Wed May 29 2019 Kristian Lesko <kristian.lesko@gooddata.com> - 1.8-1
- Add label processing to ipamanager.tools.QueryTool
* Tue May 28 2019 Kristian Lesko <kristian.lesko@gooddata.com> - 1.7-2
- Make ipamanager.tools.QueryTool easier to import
* Tue May 28 2019 Kristian Lesko <kristian.lesko@gooddata.com> - 1.7-1
- Add a query tool into ipamanager.tools
* Thu May 23 2019 Kristian Lesko <kristian.lesko@gooddata.com> - 1.6-2
- Do not re-add logging handlers if already setup
* Tue May 14 2019 Kristian Lesko <kristian.lesko@gooddata.com> - 1.6-1
- Support includes in settings file
* Tue May 14 2019 Kristian Lesko <kristian.lesko@gooddata.com> - 1.5-1
- Implement NSCA alerting plugin
* Fri Apr 26 2019 Kristian Lesko <kristian.lesko@gooddata.com> - 1.4-1
- Support round-trip (load & save) of configuration
* Wed Mar 27 2019 Kristian Lesko <kristian.lesko@gooddata.com> - 1.3-1
- Support logging to syslog as well
* Thu Mar 14 2019 Kristian Lesko <kristian.lesko@gooddata.com> - 1.2-1
- Implement group nesting limit setting
* Fri Mar 01 2019 Kristian Lesko <kristian.lesko@gooddata.com> - 1.1-3
- Only lock dependencies in specfile, not in requirements.txt
* Thu Feb 28 2019 Kristian Lesko <kristian.lesko@gooddata.com> - 1.1-2
- Define minimum version for dependencies
* Wed Jan 30 2019 Tomas Bouma <tomas.bouma@gooddata.com> - 1.1-1
- Add support for templates
* Fri Jan 25 2019 Kristian Lesko <kristian.lesko@gooddata.com> - 1.0-1
- Migrate the tool from the original repository
