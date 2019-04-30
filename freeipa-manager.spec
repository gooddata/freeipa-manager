Name:           freeipa-manager
Version:        1.4
Release:        1%{?dist}
Summary:        FreeIPA entity provisioning tool

License:        BSD License 2.0
URL:            https://github.com/gooddata/freeipa-manager
Source0:        %{name}.tar.gz

Requires:       python
Requires:       gdc-python-common
Requires:       PyYAML >= 3.10
Requires:       python-requests >= 2.6.0
Requires:       python-sh >= 1.11
Requires:       python-voluptuous >= 0.8.5
Requires:       python2-yamllint >= 1.8.1
BuildRequires:  python-setuptools python-psutil pytest
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

%files
%defattr(-,root,root,-)
%{python_sitelib}/freeipa_manager*
%{python_sitelib}/ipamanager*
%{_bindir}/ipamanager
%{_bindir}/ipamanager-pull-request

%changelog
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
