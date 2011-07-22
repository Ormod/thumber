%{!?python_sitearch: %define python_sitearch %(%{__python} -c "from distutils.sysconfig import get_python_lib; print get_python_lib(1)")}

Name:           thumber
Version:        %{version}
Release:        %{release}%{?dist}
Summary:        library for creating thumbnails and indexing them

Group:          System Environment/Libraries
License:        MIT
Source0:        %{name}-%{full_version}.tar.gz

BuildArch:	noarch
BuildRequires:  python-devel

%description
Thumber is a library for creating thumbnails and more importantly, an index
for them.  The primary use case for this library is to create n+1 thumbnails
out of a single media file and then create a single blob out of these with
an index for easy access to individual thumbnails.

%prep
%setup -q -n %{name}-%{full_version}


%build
CFLAGS="$RPM_OPT_FLAGS" %{__python} setup.py build


%install
rm -rf $RPM_BUILD_ROOT
%{__python} setup.py install --skip-build --root $RPM_BUILD_ROOT


%clean
rm -rf $RPM_BUILD_ROOT


%files
%defattr(-,root,root,-)
%doc README LICENSE
# For arch-specific packages: sitearch
%{_bindir}/*
%{python_sitelib}/*


%changelog
* Mon Jan 28 2011 Oskari Saarenmaa <oskari@saarenmaa.fi> - 0.0-0
- Initial.
