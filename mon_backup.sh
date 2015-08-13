#/bin/bash

#set -x

# Normally this script should be run by cron periodically.
# Crontab example:
# "30 18 * * * MON_NODES="node-18 node-9 node-2" BACKUP_HOSTS="node-2 node-18 node-9" /root/mon_backup.sh"

# BACKUP_HOSTS should be chosen carefully. Like CEPH failure domain,
# the remote host should reside on another rack, dc or even in the cloud,
# for best safty. And those hosts should be accessed w/o password.
export BACKUP_HOSTS=${BACKUP_HOSTS:-node-9 node-2 node-18}

export BACKUP_DIR=${BACKUP_DIR:-/var/ceph-bkp-dont-remove/mon}

export MON_NODES=${MON_NODES:-node-2 node-9 node-18}

# Keep at most $MAX_COPIES backups
export MAX_COPIES=${MAX_COPIES:-3}

DATE=`date '+%y-%m-%d-%T'`
BACKUP_DIR_DATE=$BACKUP_DIR/$DATE
echo Backuping CEPH mon data to $BACKUP_DIR on $BACKUP_HOSTS.

trim_extras() {
	dates=`ssh $1 ls -t $BACKUP_DIR 2>/dev/null`
	i=1
	for d in $dates; do
		if [ $i -gt $MAX_COPIES ]; then
			ssh $1 rm -rf $BACKUP_DIR/$d 2>/dev/null
		fi
		i=`expr $i + 1`
	done
}

backup_mon_node() {
	BACKUP_DIR_PER_NODE=$BACKUP_DIR_DATE/$1
	echo backup monitor $1 now...
	for host in $BACKUP_HOSTS; do
		ssh $host mkdir -p $BACKUP_DIR_PER_NODE 2>/dev/null 

		#### BACKUP CRITICAL MON DATA ####
		ssh $1 scp -r -p /etc/ceph $host:$BACKUP_DIR_PER_NODE 2>/dev/null
		ssh $1 scp -r -p /var/lib/ceph/bootstrap-mds $host:$BACKUP_DIR_PER_NODE 2>/dev/null
		ssh $1 scp -r -p /var/lib/ceph/bootstrap-osd $host:$BACKUP_DIR_PER_NODE 2>/dev/null
		ssh $1 scp -r -p /var/lib/ceph/mds $host:$BACKUP_DIR_PER_NODE 2>/dev/null
		ssh $1 scp -r -p /var/lib/ceph/mon $host:$BACKUP_DIR_PER_NODE 2>/dev/null
		#### TRIM EXTRA BACKUPS      #####
		trim_extras $host
		##################################
	done
	echo backup monitor $1 done.
}

for m in $MON_NODES; do
	backup_mon_node $m
done

exit
