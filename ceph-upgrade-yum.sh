#!/bin/bash
#
# -*- mode: c; c-basic-offset: 4; indent-tabs-mode: nil; -*-
# vim:expandtab:shiftwidth=4:tabstop=4:

# This script is only used to upgrade one single ceph node.
# Currently, only centos is supported and verified on centos 6.5.
# In future, may add support to other distributions, like ubuntu.
#
# After successfully upgrade all ceph node, need to restart ceph services
# manually, in the order of mon/osd/mds/gw per official guide.

set -x

export TMP=${TMP:-/tmp}
export LOG=${LOG:-./upgrade.`whoami`.log}
export DNS_CONF=${DNS_CONF:-dns.example}
export DNS_DEFAULT=${DNS_DEFAULT:-/etc/resolv.conf}
export RELEASE=${RELEASE:-firefly}

ABSOLUT_PWD=`pwd`
HOSTNAME=`hostname -s`
dns_is_changed=0

prepare_dns() {
    # Can we access ceph repo? if not, we may fail bec DNS issue.
    # Note, the DNS issue should vary case by case, provide your correct
    # DNS via DNS_CONF env.
    wget http://ceph.com/rpm-firefly/el6/x86_64/repodata/repomd.xml
    if [ $? -eq 0 ]; then
        rm repomd.xml
        return
    fi

    dns_is_changed=1
    [ -f "$DNS_CONF" ] && cp $DNS_DEFAULT $DNS_DEFAULT.bkp && cp $DNS_CONF $DNS_DEFAULT
    cat $DNS_DEFAULT
}

restore_dns() {
    if [ $dns_is_changed -eq 0 ]; then
        return
    fi
    [ -f "$DNS_DEFAULT.bkp" ] && cp $DNS_DEFAULT.bkp $DNS_DEFAULT && rm $DNS_DEFAULT.bkp 
    cat $DNS_DEFAULT
}

resolve_possible_conflict() {
    rpm -qa | grep pushy | grep -v python
    if [ $? -eq 0 ]; then
        rpm -e pushy --nodeps
    fi
    rpm -qa | grep ceph-release
    if [ $? -eq 0 ]; then
        rpm -e ceph-release
    fi
}

install_yum_repo() {
    rpm -qa | grep epel
    if [ $? -ne 0 ]; then
        rpm -ivh $ABSOLUT_PWD/rpm/epel-release*.rpm
    fi
    cp $ABSOLUT_PWD/yum.repos.d/Cent*.repo /etc/yum.repos.d/
    cp $ABSOLUT_PWD/yum.repos.d/ceph*.repo /etc/yum.repos.d/
}

upgrade_ceph() {
    yum install ceph-deploy python-pushy -y
    [ $? -ne 0 ] && exit 
    ceph-deploy install --release $RELEASE $HOSTNAME
    [ $? -ne 0 ] && exit 
    echo VERSION: `ceph --version`
}

MON_NODES="node-56 node-57 node-58"
OSD_NODES="node-75 node-76 node-89"
CLI_NODES="node-47 node-46 node-65 node-48 node-50 node-42 node-59 node-41 node-49"
ALL_NODES="$MON_NODES $OSD_NODES $CLI_NODES"
check_after_upgrade() {
    for h in $ALL_NODES; do
        ssh $h ceph --version
    done
}


[ -f "$LOG" ] && mv $LOG $LOG.old
touch $LOG

prepare_dns >> $LOG
resolve_possible_conflict >> $LOG 
install_yum_repo >> $LOG 
upgrade_ceph >> $LOG 
restore_dns >> $LOG


