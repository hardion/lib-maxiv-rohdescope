%define name python-rohdescope
%define version 0.4.2
%define unmangled_version 0.4.2
%define unmangled_version 0.4.2
%define release 1%{?dist}.maxlab

Summary: Library for remote communication with the R&S oscilloscopes.
Name: %{name}
Version: %{version}
Release: %{release}
Source0: %{name}-%{unmangled_version}.tar.gz
License: GPLv3
Group: Development/Libraries
BuildRoot: %{_tmppath}/%{name}-%{version}-%{release}-buildroot
Prefix: %{_prefix}
BuildArch: noarch
Vendor: Vincent Michel; Paul Bell <vincent.michel@maxlab.lu.se; paul.bell@maxlab.lu.se>
Requires: python-vxi11 >= 0.7.1
Url: http://www.maxlab.lu.se
BuildRequires: python-setuptools

%description
python-rohdescope
=================

Library for Rohde and Schwarz oscilloscopes.

Information
-----------

 - Package: python-rohdescope
 - Repo:    [lib-maxiv-rohdescope][rohdescope]

[rohdescope]: https://github.com/MaxIV-KitsControls/lib-maxiv-rohdescope

Requirement
-----------

 - VXI-11: [python-vxi11][vxi11] >= 0.7.1

[vxi11]: https://github.com/MaxIV-KitsControls/python-vxi11

Hardware
--------

The library has been tested with the following hardwares:

| Scope  | Reference | Firmware |
|--------|-----------|----------|
| RTM    | 2054      | 05.502   |
| RTO    | 1004      | 2.15.2.0 |

Contact
-------

- Vincent Michel: vincent.michel@maxlab.lu.se
- Paul Bell:      paul.bell@maxlab.lu.se


%prep
%setup -n %{name}-%{unmangled_version} -n %{name}-%{unmangled_version}

%build
python setup.py build

%install
python setup.py install --single-version-externally-managed -O1 --root=$RPM_BUILD_ROOT --record=INSTALLED_FILES

%clean
rm -rf $RPM_BUILD_ROOT

%files -f INSTALLED_FILES
%defattr(-,root,root)
