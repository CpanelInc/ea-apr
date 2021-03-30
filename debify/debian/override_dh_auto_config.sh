#!/bin/bash

source debian/vars.sh

# regenerate configure script etc.
./buildconf
# Forcibly prevent detection of shm_open (which then picks up but
# does not use -lrt).
export ac_cv_search_shm_open=no
./configure \
        --with-devrandom=/dev/urandom \
        --prefix=$prefix_dir \
        --libdir=$prefix_lib \
        --with-installbuilddir=$prefix_lib/apr-$aprver/build \
        apr_lock_method=USE_SYSVSEM_SERIALIZE
make 
