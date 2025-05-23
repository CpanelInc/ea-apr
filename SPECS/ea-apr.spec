%global ns_name ea
%global pkgname %{ns_name}-apr

%define aprver 1
%define prefix_name %{pkgname}16
%define prefix_dir /opt/cpanel/%{prefix_name}
%define prefix_lib %{prefix_dir}/%{_lib}
%define prefix_bin %{prefix_dir}/bin
%define prefix_inc %{prefix_dir}/include
%define prefix_data %{prefix_dir}/share
%define ea_openssl_ver 1.1.1d-1

# Arches on which the multilib apr.h hack is needed:
%define multilib_arches %{ix86} ia64 ppc ppc64 s390 s390x x86_64

%if 0%{?rhel} >= 10
# https://docs.fedoraproject.org/en-US/packaging-guidelines/#_brp_buildroot_policy_scripts
%global __brp_remove_la_files %nil
%endif

Summary: Apache Portable Runtime library
Name: %{pkgname}
Version: 1.7.6

# Doing release_prefix this way for Release allows for OBS-proof versioning, See EA-4540 for more details
%define release_prefix 1
Release: %{release_prefix}%{?dist}.cpanel
# ASL 2.0: everything
# ISC: network_io/apr-1.4.6/network_io/unix/inet_?to?.c
# BSD with advertising: strings/apr_snprintf.c, strings/apr_fnmatch.c,
#                   include/apr_fnmatch.h, misc/unix/getopt.c,
#                   file_io/unix/mktemp.c, strings/apr_strings.c
# BSD (3-clause): strings/apr_strnatcmp.c, include/apr_strings.h
License: ASL 2.0 and BSD with advertising and ISC and BSD
Group: System Environment/Libraries
URL: http://apr.apache.org/
Vendor: cPanel, Inc.
Source0: http://www.apache.org/dist/apr/apr-%{version}.tar.gz
Source1: apr-wrapper.h
Source2: macros.ea-apr
Patch1: 0001-apr-config-Avoid-using-L-if-libdir-is-in-usr.patch
Patch2: 0002-Update-pkg-config-variables.patch
Patch3: 0003-Add-apr_stat_fd-to-file-io-layer.patch
Patch4: 0004-Check-for-NULL-mutex-in-apr_global_mutex_child_init.patch
BuildRoot: %{_tmppath}/%{name}-%{version}-%{release}-buildroot
BuildRequires: autoconf, libtool, libuuid-devel

%if 0%{?rhel} == 8
BuildRequires: python36
%else
    %if 0%{?rhel} >= 9
BuildRequires: python3
    %else
BuildRequires: python
    %endif
%endif

%if 0%{?rhel} > 7
# In C8 we use system openssl. See DESIGN.md in ea-openssl11 git repo for details
BuildRequires: openssl openssl-devel
Requires: openssl
%else
BuildRequires: ea-openssl11 >= %{ea_openssl_ver}, ea-openssl11-devel >= %{ea_openssl_ver}
%endif

# To enable SCTP support
BuildRequires: lksctp-tools-devel

%description
The mission of the Apache Portable Runtime (APR) is to provide a
free library of C data structures and routines, forming a system
portability layer to as many operating systems as possible,
including Unices, MS Win32, BeOS and OS/2.

%package devel
Group: Development/Libraries
Summary: APR library development kit
Conflicts: subversion-devel < 0.20.1-2
Requires: %{pkgname}, pkgconfig

%description devel
This package provides the support files which can be used to
build applications using the APR library.  The mission of the
Apache Portable Runtime (APR) is to provide a free library of
C data structures and routines.

%prep
%setup -q -n apr-%{version}
%patch1 -p1 -b .libdir
%patch2 -p1 -b .pkgconf
%patch3 -p1 -b .symlink
%patch4 -p1 -b .nullmutex

%if 0%{?rhel} < 8
export CFLAGS="-I/opt/cpanel/ea-openssl11/include"
export LDFLAGS="-L/opt/cpanel/ea-openssl11/lib -R/opt/cpanel/ea-openssl11/lib"
%endif

%build

# regenerate configure script etc.
./buildconf

# Forcibly prevent detection of shm_open (which then picks up but
# does not use -lrt).
export ac_cv_search_shm_open=no

./configure \
        --with-devrandom=/dev/urandom \
        --prefix=%{prefix_dir} \
        --libdir=%{prefix_lib} \
        --with-installbuilddir=%{prefix_lib}/apr-%{aprver}/build \
        apr_lock_method=USE_SYSVSEM_SERIALIZE
make %{?_smp_mflags}

%install
rm -rf $RPM_BUILD_ROOT
make install DESTDIR=$RPM_BUILD_ROOT

mkdir -p $RPM_BUILD_ROOT/%{prefix_data}/aclocal
install -m 644 build/find_apr.m4 $RPM_BUILD_ROOT/%{prefix_data}/aclocal

# Trim exported dependecies
sed -ri '/^dependency_libs/{s,-l(uuid|crypt) ,,g}' \
      $RPM_BUILD_ROOT%{prefix_lib}/libapr*.la
# Also set pkgconfig to reference the right defs file
sed -ri '/^LIBS=/{s,-l(uuid|crypt) ,,g;s/  */ /g};/pkg-config/{s,apr-%{aprver},%{prefix_name}-%{aprver},g}' \
      $RPM_BUILD_ROOT%{prefix_bin}/apr-%{aprver}-config
sed -ri '/^Libs/{s,-l(uuid|crypt) ,,g}' \
      $RPM_BUILD_ROOT%{prefix_lib}/pkgconfig/apr-%{aprver}.pc

# In order for apr and our package to coexist, we have to name our
# pkgconfig files something else
mkdir -p $RPM_BUILD_ROOT%{_libdir}/pkgconfig
mv $RPM_BUILD_ROOT%{prefix_lib}/pkgconfig/apr-%{aprver}.pc $RPM_BUILD_ROOT%{_libdir}/pkgconfig/%{prefix_name}-%{aprver}.pc

# Set up the macros file
install -d -m 755 $RPM_BUILD_ROOT%{_sysconfdir}/rpm
sed -e 's/@APR_NAME@/%{prefix_name}/g' \
    -e 's/@APR_VER@/%{aprver}/g' \
    -e 's,@APR_DIR@,%{prefix_dir},g' \
    -e 's/@NAMESPACE@/%{ns_name}_/g' \
    %{SOURCE2} > $RPM_BUILD_ROOT%{_sysconfdir}/rpm/macros.%{pkgname}

%ifarch %{multilib_arches}
# Ugly hack to allow parallel installation of 32-bit and 64-bit apr-devel
# packages:
mv $RPM_BUILD_ROOT%{prefix_inc}/apr-%{aprver}/apr.h \
   $RPM_BUILD_ROOT%{prefix_inc}/apr-%{aprver}/apr-%{_arch}.h
install -c -m644 %{SOURCE1} $RPM_BUILD_ROOT%{prefix_inc}/apr-%{aprver}/apr.h
%endif

# Unpackaged files:
rm -f $RPM_BUILD_ROOT%{prefix_lib}/apr.exp

%check
# Fail if LFS support isn't present in a 32-bit build, since this
# breaks ABI and the soname doesn't change: see #254241
if grep 'define SIZEOF_VOIDP 4' include/apr.h \
   && ! grep off64_t include/apr.h; then
  cat config.log
  : LFS support not present in 32-bit build
  exit 1
fi

%clean
rm -rf $RPM_BUILD_ROOT

%post -p /sbin/ldconfig

%postun -p /sbin/ldconfig

%files
%defattr(0644,root,root,0755)
%doc CHANGES LICENSE NOTICE
%dir %{prefix_dir}
%dir %{prefix_lib}
%attr(0755,root,root) %{prefix_lib}/libapr-%{aprver}.so.*

%files devel
%defattr(0644,root,root,0755)
%doc docs/APRDesign.html docs/canonical_filenames.html
%doc docs/incomplete_types docs/non_apr_programs
%dir %{prefix_bin}
%attr(0755,root,root) %{prefix_bin}/apr-%{aprver}-config
%if 0%{?rhel} < 10
%attr(0755,root,root) %{prefix_lib}/libapr-%{aprver}.*a
%else
# On AlmaLinux 10, a "warning" appears in the log saying since the file libapr-1.la does not have
# a shebang, rpm removed the executable bits.
# We will see where this goes, but if the executable bit is needed I will need to prepend a shebang on the
# files.  The contents of the file are just "var=value" hopefully sourced into other scripts.
# This remains to be seen
%attr(0644,root,root) %{prefix_lib}/libapr-%{aprver}.*a
%endif
%attr(0755,root,root) %{prefix_lib}/libapr-%{aprver}.so
%{_libdir}/pkgconfig/*.pc
%dir %{prefix_lib}/apr-%{aprver}
%dir %{prefix_lib}/apr-%{aprver}/build
%attr(0755,root,root) %{prefix_lib}/apr-%{aprver}/build/*
%dir %{prefix_inc}
%dir %{prefix_inc}/apr-%{aprver}
%{prefix_inc}/apr-%{aprver}/*.h
%{prefix_data}/aclocal/find_apr.m4
%{_sysconfdir}/rpm/macros.%{pkgname}

%changelog
* Fri May 16 2025 Cory McIntire <cory.mcintire@webpros.com> - 1.7.6-1
- EA-12870: Update ea-apr from v1.7.5 to v1.7.6

* Mon Aug 26 2024 Cory McIntire <cory@cpanel.net> - 1.7.5-1
- EA-12350: Update apr from v1.7.4 to v1.7.5
- SECURITY: CVE-2023-49582: Apache Portable Runtime (APR):
     Unexpected lax shared memory permissions (cve.mitre.org)
     Lax permissions set by the Apache Portable Runtime library on
     Unix platforms would allow local users read access to named
     shared memory segments, potentially revealing sensitive
     application data.
     This issue does not affect non-Unix platforms, or builds with
     APR_USE_SHMEM_SHMGET=1 (apr.h)
     Users are recommended to upgrade to APR version 1.7.5, which
     fixes this issue.
     Credits: Thomas Stangner


* Mon Apr 17 2023 Cory McIntire <cory@cpanel.net> - 1.7.4-1
- EA-11357: Update apr from v1.7.3 to v1.7.4

* Fri Mar 31 2023 Cory McIntire <cory@cpanel.net> - 1.7.3-1
- EA-11326: Update apr from v1.7.2 to v1.7.3

* Thu Feb 02 2023 Tim Mullin <tim@cpanel.net> - 1.7.2-1
- EA-11198: Update apr from v1.7.0 to v1.7.2
- CVE-2022-24963
    Integer Overflow or Wraparound vulnerability in apr_encode functions of
    Apache Portable Runtime (APR) allows an attacker to write beyond bounds
    of a buffer.
- CVE-2021-35940
    Restore fix for out-of-bounds array dereference in apr_time_exp*() functions.
    (This issue was addressed as CVE-2017-12613 in APR 1.6.3 and
    later 1.6.x releases, but was missing in 1.7.0.)

* Thu Sep 29 2022 Julian Brown <julian.brown@cpanel.net> - 1.7.0-8
- ZC-10009: Add changes so that it builds on AlmaLinux 9

* Mon Feb 28 2022 Tim Mullin <tim@cpanel.net> - 1.7.0-7
- EA-10477: Check for NULL mutex in apr_global_mutex_child_init

* Wed Aug 25 2021 Tim Mullin <tim@cpanel.net> - 1.7.0-6
- EA-10069: Patch 1.7.0 for CVE-2021-35940

* Mon Nov 23 2020 Julian Brown <julian.brown@cpanel.net> - 1.7.0-5
- ZC-8005: Remove ea-openssl11 on C8

* Thu May 07 2020 Julian Brown <julian.brown@cpanel.net> - 1.7.0-4
- ZC-6743: Build on C8

* Tue Sep 24 2019 Daniel Muey <dan@cpanel.net> - 1.7.0-3
- ZC-4361: Update ea-openssl requirement to v1.1.1 (ZC-5583)

* Tue Jun 26 2019 Tim Mullin <tim@cpanel.net> - 1.7.0-2
- EA-8542: Change apr_lock_method to USE_SYSVSEM_SERIALIZE

* Thu May 16 2019 Cory McIntire <cory@cpanel.net> - 1.7.0-1
- EA-8471: Update apr from v1.6.5 to v1.7.0

* Wed Feb 13 2019 Cory McIntire <cory@cpanel.net> - 1.6.5-1
- EA-8225: Update to version 1.6.5

* Mon Apr 16 2018 Rishwanth Yeddula <rish@cpanel.net> - 1.6.3-2
- EA-7382: Update dependency on ea-openssl to require the latest version with versioned symbols.

* Thu Mar 22 2018 Rishwanth Yeddula <rish@cpanel.net> - 1.6.3-1
- EA-7242: Update to 1.6.3

* Mon Mar 20 2018 Cory McIntire <cory@cpanel.net> - 1.5.3-9
- ZC-3552: Version ea-openssl requirements

* Wed Nov 29 2017 Dmitriy Kasyanov <dkasyanov@cloudlinux.com> - 1.5.2-9
- CVE-2017-12613: Out-of-bounds array deref in apr_time_exp*() functions

* Thu Jun 08 2017 Jacob Perkins <jacob.perkins@cpanel.net> - 1.5.2-8
- Build against ea-openssl

* Tue Apr 18 2017 Sergey Fokin <https://github.com/titan-dn> - 1.5.2-7
- fix file conflicts with system apr

* Fri Dec 16 2016 Jacob Perkins <jacob.perkins@cpanel.net> - 1.5.2-6
- Added vendor field

* Fri Dec 02 2016 S. Kurt Newman <kurt.newman@cpanel.net> - 1.5.2-5
- libdir is removed when the rpm is uninstalled (EA-5169)

* Tue Oct 25 2016 Edwin Buck <e.buck@cpanel.net> - 1.5.2-4
- EA-5473: Added function to do stat on a file descriptor.

* Thu Jun 16 2016 Dan Muey <dan@cpanel.net> - 1.5.2-3
- EA-4383: Update Release value to OBS-proof versioning

* Thu Mar 10 2016 David Nielson <david.nielson@cpanel.net> - 1.5.2-2
- Removed Cloudlinux patch

* Tue Oct 13 2015 Jacob Perkins <jacob.perkins@cpanel.net> - 1.5.2-1
- Updated to version 1.5.2 via update_pkg.pl

* Fri Jul 31 2015 Trinity Quirk <trinity.quirk@cpanel.net> 1.5.1-5
- Added macro handling for dependency resolution

* Mon Jun 29 2015 Matt Dees <matt@cpanel.net> 1.5.1-4
- Move ea-apr to /opt/cpanel/ea-apr15

* Thu Mar 26 2015 Trinity Quirk <trinity.quirk@cpanel.net> - 1.5.1-3
- Renamed to ea-apr, added conflicts with apr*

* Mon Mar 23 2015 Trinity Quirk <trinity.quirk@cpanel.net> - 1.5.1-2
- Added CloudLinux patch

* Fri Feb 27 2015 Trinity Quirk <trinity.quirk@cpanel.net> - 1.5.1-1
- Upgraded to 1.5.1

* Fri Jan 24 2014 Daniel Mach <dmach@redhat.com> - 1.4.8-3
- Mass rebuild 2014-01-24

* Fri Dec 27 2013 Daniel Mach <dmach@redhat.com> - 1.4.8-2
- Mass rebuild 2013-12-27

* Mon Jun 24 2013 Joe Orton <jorton@redhat.com> - 1.4.8-1
- update to 1.4.8 (#976972)

* Wed May 29 2013 Joe Orton <jorton@redhat.com> - 1.4.6-7
- update config.* for aarch64 (#925009)

* Wed Feb 13 2013 Fedora Release Engineering <rel-eng@lists.fedoraproject.org> - 1.4.6-6
- Rebuilt for https://fedoraproject.org/wiki/Fedora_19_Mass_Rebuild

* Wed Dec 12 2012 Jan Kaluza <jkaluza@redhat.com> - 1.4.6-5
- fix strict-aliasing gcc warning
- remove unused SHA384 and SHA512 code

* Thu Nov 22 2012 Joe Orton <jorton@redhat.com> - 1.4.6-4
- update license

* Wed Jul 18 2012 Fedora Release Engineering <rel-eng@lists.fedoraproject.org> - 1.4.6-3
- Rebuilt for https://fedoraproject.org/wiki/Fedora_18_Mass_Rebuild

* Fri Jul  6 2012 Joe Orton <jorton@redhat.com> - 1.4.6-2
- pull fix for apr_mcast_hops from upstream

* Tue Feb 14 2012 Bojan Smojver <bojan@rexursive.com> - 1.4.6-1
- bump up to 1.4.6

* Thu Jan 12 2012 Fedora Release Engineering <rel-eng@lists.fedoraproject.org> - 1.4.5-3
- Rebuilt for https://fedoraproject.org/wiki/Fedora_17_Mass_Rebuild

* Thu Oct 13 2011 Joe Orton <jorton@redhat.com> - 1.4.5-2
- remove deepbind patch, should no longer be necessary

* Fri May 20 2011 Bojan Smojver <bojan@rexursive.com> - 1.4.5-1
- bump up to 1.4.5

* Tue May 10 2011 Bojan Smojver <bojan@rexursive.com> - 1.4.4-2
- fix top_builddir in apr_rules.mk

* Mon May  9 2011 Bojan Smojver <bojan@rexursive.com> - 1.4.4-1
- bump up to 1.4.4
- CVE-2011-0419

* Wed Mar  2 2011 Joe Orton <jorton@redhat.com> - 1.4.2-3
- work around alising issue in ring macros (upstream PR 50190)
- fix buildconf with newer libtool (#670621)

* Mon Feb 07 2011 Fedora Release Engineering <rel-eng@lists.fedoraproject.org> - 1.4.2-2
- Rebuilt for https://fedoraproject.org/wiki/Fedora_15_Mass_Rebuild

* Sat Dec  4 2010 Joe Orton <jorton@redhat.com> - 1.4.2-1
- update to 1.4.2
- always enable SCTP support (#659815)

* Sun Oct 25 2009 Bojan Smojver <bojan@rexursive.com> - 1.3.9-3
- remove uuid/crypt libs from pkg-config file (#511522)

* Mon Sep 28 2009 Bojan Smojver <bojan@rexursive.com> - 1.3.9-2
- revert use of accept4(), dup3() and epoll_create1()

* Fri Sep 25 2009 Bojan Smojver <bojan@rexursive.com> - 1.3.9-1
- bump up to 1.3.9

* Thu Aug  6 2009 Bojan Smojver <bojan@rexursive.com> - 1.3.8-1
- bump up to 1.3.8
- CVE-2009-2412
- allocator alignment fixes

* Sun Jul 26 2009 Bojan Smojver <bojan@rexursive.com> - 1.3.7-2
- include apr_cv_sock_cloexec too

* Sun Jul 26 2009 Bojan Smojver <bojan@rexursive.com> - 1.3.7-1
- bump up to 1.3.7

* Fri Jul 24 2009 Fedora Release Engineering <rel-eng@lists.fedoraproject.org> - 1.3.6-2
- Rebuilt for https://fedoraproject.org/wiki/Fedora_12_Mass_Rebuild

* Wed Jul 15 2009 Bojan Smojver <bojan@rexursive.com> - 1.3.6-1
- bump up to 1.3.6

* Tue Jun 30 2009 Joe Orton <jorton@redhat.com> 1.3.5-5
- BR libuuid-devel instead of e2fsprogs-devel

* Mon Jun  8 2009 Bojan Smojver <bojan@rexursive.com> - 1.3.5-4
- bump up to 1.3.5

* Mon Feb 23 2009 Fedora Release Engineering <rel-eng@lists.fedoraproject.org> - 1.3.3-4
- Rebuilt for https://fedoraproject.org/wiki/Fedora_11_Mass_Rebuild

* Wed Feb  4 2009 Joe Orton <jorton@redhat.com> 1.3.3
- fix build with libtool 2.2

* Fri Jan  2 2009 Joe Orton <jorton@redhat.com> 1.3.3
- rebuild

* Sat Aug 16 2008 Bojan Smojver <bojan@rexursive.com> - 1.3.3-1
- bump up to 1.3.3

* Wed Jul 16 2008 Bojan Smojver <bojan@rexursive.com> - 1.3.2-2
- ship find_apr.m4, fix bug #455189

* Thu Jun 19 2008 Bojan Smojver <bojan@rexursive.com> - 1.3.2-1
- bump up to 1.3.2

* Sun Jun  1 2008 Bojan Smojver <bojan@rexursive.com> - 1.3.0-1
- bump up to 1.3.0

* Tue Feb 19 2008 Fedora Release Engineering <rel-eng@fedoraproject.org> - 1.2.12-2
- Autorebuild for GCC 4.3

* Mon Nov 26 2007 Bojan Smojver <bojan@rexursive.com> 1.2.12-1
- bump up to 1.2.12
- add dist
- remove a comment from apr-1.2.7-psprintfpi.patch (applied upstream)

* Tue Sep 18 2007 Joe Orton <jorton@redhat.com> 1.2.11-2
- fix %%check for non-multilib 64-bit platforms

* Sun Sep  9 2007 Bojan Smojver <bojan@rexursive.com> 1.2.11-1
- bump up to 1.2.11
- drop openlfs patch (fixed upstream)

* Sun Sep  2 2007 Joe Orton <jorton@redhat.com> 1.2.9-4
- fix API/ABI of 32-bit builds (#254241)

* Tue Aug 21 2007 Joe Orton <jorton@redhat.com> 1.2.9-2
- fix License

* Mon Jun 25 2007 Bojan Smojver <bojan@rexursive.com> 1.2.9-1
- bump up to 1.2.9

* Mon Jun  4 2007 Joe Orton <jorton@redhat.com> 1.2.8-7
- drop %%check section entirely; inappropriate to run in build env.

* Fri Mar 30 2007 Joe Orton <jorton@redhat.com> 1.2.8-6
- merge review (#225253): drop .a archive; drop use of CC/CXX,
  use BuildRequires; drop old Conflicts; URL reference for Source

* Thu Mar 22 2007 Joe Orton <jorton@redhat.com> 1.2.8-5
- drop the doxygen documentation (which causes multilib conflicts)

* Thu Feb 15 2007 Joe Orton <jorton@redhat.com> 1.2.8-4
- add BR for python

* Thu Feb 15 2007 Joe Orton <jorton@redhat.com> 1.2.8-3
- update to pick up new libtool, drop specific gcc requirement

* Mon Dec  4 2006 Joe Orton <jorton@redhat.com> 1.2.8-2
- update to 1.2.8

* Wed Jul 19 2006 Joe Orton <jorton@redhat.com> 1.2.7-10
- fix buildconf with autoconf 2.60 (#199067)

* Wed Jul 12 2006 Jesse Keating <jkeating@redhat.com> 1.2.7-9.1
- rebuild

* Mon Jun 19 2006 Joe Orton <jorton@redhat.com> 1.2.7-9
- add fix for use of %%pI with psprintf

* Fri May 26 2006 Jakub Jelinek <jakub@redhat.com> 1.2.7-8
- rebuilt with GCC 4.1.0

* Tue May 23 2006 Joe Orton <jorton@redhat.com> 1.2.7-7
- fix another multilib conflict (#192659)

* Tue May 16 2006 Joe Orton <jorton@redhat.com> 1.2.7-6
- BR e2fsprogs-devel for libuuid

* Mon May  8 2006 Joe Orton <jorton@redhat.com> 1.2.7-4
- use multilib parallel-installation wrapper hack for apr.h

* Tue May  2 2006 Joe Orton <jorton@redhat.com> 1.2.7-3
- fix installbuilddir in apr-1-config

* Tue May  2 2006 Joe Orton <jorton@redhat.com> 1.2.7-2
- update to 1.2.7
- use pkg-config in apr-1-config to make it libdir-agnostic

* Thu Apr  6 2006 Joe Orton <jorton@redhat.com> 1.2.6-2
- update to 1.2.6

* Fri Feb 10 2006 Jesse Keating <jkeating@redhat.com> - 1.2.2-7.2
- bump again for double-long bug on ppc(64)

* Tue Feb 07 2006 Jesse Keating <jkeating@redhat.com> - 1.2.2-7.1
- rebuilt for new gcc4.1 snapshot and glibc changes

* Wed Jan  4 2006 Joe Orton <jorton@redhat.com> 1.2.2-7
- fix namespace pollution (r354824, r355464)

* Wed Jan  4 2006 Joe Orton <jorton@redhat.com> 1.2.2-6
- fix build with recent glibc (#176911)

* Tue Jan  3 2006 Jesse Keating <jkeating@redhat.com> 1.2.2-5.2
- rebuilt again

* Fri Dec 09 2005 Jesse Keating <jkeating@redhat.com>
- rebuilt

* Fri Dec  9 2005 Joe Orton <jorton@redhat.com> 1.2.2-5
- rebuild for new gcc

* Thu Dec  8 2005 Joe Orton <jorton@redhat.com> 1.2.2-4
- add apr_file_seek() fixes from upstream (r326593, r326597)

* Wed Dec  7 2005 Joe Orton <jorton@redhat.com> 1.2.2-3
- apr-1-config: strip more exports (#175124)

* Tue Dec  6 2005 Joe Orton <jorton@redhat.com> 1.2.2-2
- avoid linking against -lrt
- don't print -L${libdir} in --libs output
- don't export -lcrypt/-luuid in .la file

* Fri Dec  2 2005 Joe Orton <jorton@redhat.com> 1.2.2-1
- update to 1.2.2

* Thu Nov 24 2005 Joe Orton <jorton@redhat.com> 0.9.7-3
- use RTLD_DEEPBIND in apr_dso_open by default

* Thu Oct 20 2005 Joe Orton <jorton@redhat.com> 0.9.7-2
- update to 0.9.7

* Fri Sep 30 2005 Florian La Roche <laroche@redhat.com>
- rebuild for new gcc

* Thu Sep 15 2005 Joe Orton <jorton@redhat.com> 0.9.6-6
- don't override CFLAGS at build time
- allow setting TCP_NODELAY and TCP_CORK concurrently
- use _exit() not exit() in child if exec*() fails (upstream #30913)

* Fri Sep  9 2005 Joe Orton <jorton@redhat.com> 0.9.6-5
- add from 0.9.x branch:
 * fix for apr_{uid,gid}_* error handling (r239592)
 * fix for apr_file_ write flushing (r267192)
- add backport for use of readdir64_r (r265032, r265681, r265684)

* Mon Jul 11 2005 Florian La Roche <laroche@redhat.com>
- rebuild

* Tue May 17 2005 Joe Orton <jorton@redhat.com> 0.9.6-3
- fix apr_procattr_child_*_set error handling

* Tue Mar  1 2005 Joe Orton <jorton@redhat.com> 0.9.6-2
- have apr-devel depend on specific version of gcc
- add NOTICE to docdir

* Wed Feb  9 2005 Joe Orton <jorton@redhat.com> 0.9.6-1
- update to 0.9.6

* Wed Feb  2 2005 Joe Orton <jorton@redhat.com> 0.9.5-4
- don't disable sendfile on s390 (IBM LTC, #146891)

* Mon Nov 22 2004 Joe Orton <jorton@redhat.com> 0.9.5-3
- really fix apr-config --srcdir

* Mon Nov 22 2004 Joe Orton <jorton@redhat.com> 0.9.5-2
- fix apr-config --srcdir again

* Sun Nov 21 2004 Joe Orton <jorton@redhat.com> 0.9.5-1
- update to 0.9.5

* Mon Sep 27 2004 Joe Orton <jorton@redhat.com> 0.9.4-24
- rebuild

* Wed Sep  1 2004 Joe Orton <jorton@redhat.com> 0.9.4-23
- have -devel require apr of same V-R

* Tue Aug 31 2004 Joe Orton <jorton@redhat.com> 0.9.4-22
- backport fixes from HEAD:
 * correct implementation of nested mutexes
 * support for POSIX semaphores on LP64 platforms

* Thu Jul 15 2004 Joe Orton <jorton@redhat.com> 0.9.4-21
- rebuild for another attempt at using sem_open

* Tue Jul 13 2004 Joe Orton <jorton@redhat.com> 0.9.4-20
- move sticky/suid bits outside APR_OS_DEFAULT bitmask (Greg Hudson)

* Thu Jul  1 2004 Joe Orton <jorton@redhat.com> 0.9.4-19
- rebuild

* Wed Jun 30 2004 Joe Orton <jorton@redhat.com> 0.9.4-18
- rebuild now /dev/shm is mounted

* Thu Jun 17 2004 Joe Orton <jorton@redhat.com> 0.9.4-17
- add fix for cleanup structure reuse (part of upstream #23567)

* Tue Jun 15 2004 Elliot Lee <sopwith@redhat.com>
- rebuilt

* Thu Jun 10 2004 Joe Orton <jorton@redhat.com> 0.9.4-15
- add support for setuid/setgid/sticky bits (André Malo)
- add apr_threadattr_{guardsize,stacksize}_set() (latter by Jeff Trawick)

* Mon Jun  7 2004 Joe Orton <jorton@redhat.com> 0.9.4-14
- enable posixsem and process-shared pthread mutex support, but
  ensure that sysvsem remains the default mechanism

* Mon May 24 2004 Joe Orton <jorton@redhat.com> 0.9.4-13
- entirely remove 2Gb file size limit from apr_file_copy();
  fixes "svnadmin hotcopy" on repos with >2Gb strings table
- work around getnameinfo bugs with v4-mapped addresses
- fix apr_time_exp_get() for dates in 2038 (Philip Martin)

* Thu May 13 2004 Joe Orton <jorton@redhat.com> 0.9.4-12
- use APR_LARGEFILE in apr_file_{copy,append}

* Wed Mar 24 2004 Joe Orton <jorton@redhat.com> 0.9.4-11
- add APR_LARGEFILE flag

* Mon Mar 15 2004 Joe Orton <jorton@redhat.com> 0.9.4-10
- fix configure check for mmap of /dev/zero
- just put -D_GNU_SOURCE in CPPFLAGS not _{BSD,SVID,XOPEN}_SOURCE

* Tue Mar 02 2004 Elliot Lee <sopwith@redhat.com> 0.9.4-9.1
- rebuilt

* Thu Feb 19 2004 Joe Orton <jorton@redhat.com> 0.9.4-9
- undocument apr_dir_read() ordering constraint and fix tests

* Sun Feb 15 2004 Joe Orton <jorton@redhat.com> 0.9.4-8
- rebuilt without -Wall -Werror

* Fri Feb 13 2004 Elliot Lee <sopwith@redhat.com> 0.9.4-7
- rebuilt

* Tue Feb  3 2004 Joe Orton <jorton@redhat.com> 0.9.4-6
- define apr_off_t as int/long/... to prevent it changing
  with _FILE_OFFSET_BITS on 32-bit platforms

* Mon Jan 12 2004 Joe Orton <jorton@redhat.com> 0.9.4-5
- add apr_temp_dir_get fixes from HEAD

* Thu Jan  8 2004 Joe Orton <jorton@redhat.com> 0.9.4-4
- ensure that libapr is linked against libpthread
- don't link libapr against -lnsl

* Thu Nov 13 2003 Joe Orton <jorton@redhat.com> 0.9.4-3
- -devel package no longer requires libtool

* Fri Oct  3 2003 Joe Orton <jorton@redhat.com> 0.9.4-2
- disable tests on x86_64 (#97611)

* Fri Oct  3 2003 Joe Orton <jorton@redhat.com> 0.9.4-1
- update to 0.9.4, enable tests
- ensure that libresolv is not used

* Sun Sep  7 2003 Joe Orton <jorton@redhat.com> 0.9.3-14
- use /dev/urandom (#103049)

* Thu Jul 24 2003 Joe Orton <jorton@redhat.com> 0.9.3-13
- add back CC=gcc, CXX=g++

* Tue Jul 22 2003 Nalin Dahyabhai <nalin@redhat.com> 0.9.3-12
- rebuild

* Mon Jul 14 2003 Joe Orton <jorton@redhat.com> 0.9.3-11
- work round useless autoconf 2.57 AC_DECL_SYS_SIGLIST

* Thu Jul 10 2003 Joe Orton <jorton@redhat.com> 0.9.3-10
- support --cc and --cpp arguments in apr-config

* Thu Jul  3 2003 Joe Orton <jorton@redhat.com> 0.9.3-9
- force libtool to use CC=gcc, CXX=g++

* Thu Jul  3 2003 Joe Orton <jorton@redhat.com> 0.9.3-8
- fix libtool location in apr_rules.mk

* Mon Jun 30 2003 Joe Orton <jorton@redhat.com> 0.9.3-7
- use AI_ADDRCONFIG in getaddrinfo() support (#73350)
- include a working libtool script rather than relying on
 /usr/bin/libtool (#97695)

* Wed Jun 18 2003 Joe Orton <jorton@redhat.com> 0.9.3-6
- don't use /usr/bin/libtool

* Wed Jun 04 2003 Elliot Lee <sopwith@redhat.com>
- rebuilt

* Tue May 20 2003 Joe Orton <jorton@redhat.com> 0.9.3-5
- add fix for psprintf memory corruption (CAN-2003-0245)
- remove executable bit from apr_poll.h

* Thu May  1 2003 Joe Orton <jorton@redhat.com> 0.9.3-4
- link libapr against libpthread
- make apr-devel conflict with old subversion-devel
- fix License

* Tue Apr 29 2003 Joe Orton <jorton@redhat.com> 0.9.3-3
- run ldconfig in post/postun

* Tue Apr 29 2003 Joe Orton <jorton@redhat.com> 0.9.3-2
- patch test suite to not care if IPv6 is disabled

* Mon Apr 28 2003 Joe Orton <jorton@redhat.com> 0.9.3-1
- initial build
