#!/bin/bash

source debian/vars.sh

rm -rf $DEB_INSTALL_ROOT
make install DESTDIR=$DEB_INSTALL_ROOT
mkdir -p $DEB_INSTALL_ROOT/$prefix_data/aclocal
install -m 644 build/find_apr.m4 $DEB_INSTALL_ROOT/$prefix_data/aclocal
# Trim exported dependecies
sed -ri '/^dependency_libs/{s,-l(uuid|crypt) ,,g}' \
      $DEB_INSTALL_ROOT$prefix_lib/libapr*.la
# Also set pkgconfig to reference the right defs file
sed -ri '/^LIBS=/{s,-l(uuid|crypt) ,,g;s/  */ /g};/pkg-config/{s,apr-$aprver,$prefix_name-$aprver,g}' \
      $DEB_INSTALL_ROOT$prefix_bin/apr-$aprver-config
sed -ri '/^Libs/{s,-l(uuid|crypt) ,,g}' \
      $DEB_INSTALL_ROOT$prefix_lib/pkgconfig/apr-$aprver.pc
# In order for apr and our package to coexist, we have to name our
# pkgconfig files something else
mkdir -p $DEB_INSTALL_ROOT$_libdir/pkgconfig
mv $DEB_INSTALL_ROOT$prefix_lib/pkgconfig/apr-$aprver.pc $DEB_INSTALL_ROOT$_libdir/pkgconfig/$prefix_name-$aprver.pc

# Ugly hack to allow parallel installation of 32-bit and 64-bit apr-devel
# packages:
mv $DEB_INSTALL_ROOT$prefix_inc/apr-$aprver/apr.h \
   $DEB_INSTALL_ROOT$prefix_inc/apr-$aprver/apr-x86_64.h
install -c -m644 $SOURCE1 $DEB_INSTALL_ROOT$prefix_inc/apr-$aprver/apr.h

# Unpackaged files:
rm -f $DEB_INSTALL_ROOT$prefix_lib/apr.exp \
      $DEB_INSTALL_ROOT$prefix_lib/libapr-*.a
