Name:           freeipa-manager
Version:        1.0
Release:        1%{?dist}
Summary:        FreeIPA entity provisioning tool

License:        GoodData proprietary
URL:            https://github.com/gooddata/freeipa-manager
Source0:        %{name}.tar.gz

Requires:       python
Requires:       gdc-python-common
Requires:       PyYAML
Requires:       python-requests
Requires:       python-sh
Requires:       python-voluptuous
Requires:       python2-yamllint
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
* Fri Jan 25 2019 Kristian Lesko <kristian.lesko@gooddata.com> - 1.0-1
- Migrate the tool from the original repository
