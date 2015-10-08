 #-*- coding: utf-8 -*-
import multiprocessing as mp
import os, sys
import random
from signal import signal, SIGINT, SIG_IGN, siginterrupt
import logging
import datetime
from optparse import OptionParser

# TODO
# . clone format
# . delta mode is not supported.
# . Save backup history to DB for future lookup, like history list, success
#   rate.
# . Cluster mode? Have a pool of backup/restore initiators thus avoiding single
#   point issue.
# . task cancelling to support user stop one ongoing work.

# Do complete backup every N days
g_restart_every_n_days = 7

# remote hostname and user, should access $user@$host w/o password
g_host = "node-11"
g_user = "root"

# log file
g_log = "/tmp/rbd_backup.log"

# remote pool to backup
g_remote_pool = ""

# full backup images to keep, 0 means no limitation.
g_full_backup_to_keep = 0

# the indication files are put in below directory which must be specified in
# absolute path format.
g_async_indication_dir = "/tmp/rbd_async_indication"

# the indication file postfix to indicate its status
g_async_indication_ongoing = ".ongoing"
g_async_indication_done = ".done"
g_async_indication_fail = ".fail"

# date & timestamp
date = str(datetime.datetime.today().date())
timestamp = str(datetime.datetime.today().time())
current = date + '.' + timestamp

# postfix
postfix_image = ".bkp.image"
postfix_auto_image = ".bkp.image.auto" # not used
postfix_tmp_image = ".tmp"

# backup chain type, the head branch is active, all others are passive
# TODO add more comments for active/passive
active_branch_type = "active"
passive_branch_type = "passive"

# Simple wrapper,
# For some cases, there is no output for shell command. $? is the only way to
# tell the execution result. So let succeed or not as last element in return
# value.
def execute_cmd(cmd):
    cmd = cmd + "; echo $?"
    res = os.popen(cmd).read()
    rc = int(res.split('\n')[-2])
    output = res.split('\n')
    del output[-1]
    del output[-1]
    return rc, output

def cleanup_after_full_backup(image):
    """
    Keep at most g_full_backup_to_keep images that are most up to date.
    Drop the others.
    Also, purge all snapshots as no need to keep them.
    """
    if g_full_backup_to_keep == 0:
        return

    cmd = "ssh %s@%s rbd -p %s ls 2>/dev/null | grep %s | grep .image" \
            % (g_user, g_host, g_remote_pool, image)
    rc, output = execute_cmd(cmd)
    if rc != 0:
        sys.exit(rc)

    if len(output) > g_full_backup_to_keep:
        num_to_rm = len(output) - g_full_backup_to_keep
        for i in range(0, num_to_rm):
            t = output[i]
            logging.debug("cleanup extra image %s ...", t)
            cmd = "ssh %s@%s rbd -p %s rm %s 2>/dev/null" % (g_user, g_host, g_remote_pool, t)
            rc2, output2 = execute_cmd(cmd)
            if rc2 != 0:
                logging.debug("cleanup: falied to remove extra backup image.")

def is_first_backup(pool, image):
    """
    return True or False
    """
    cmd = "ssh %s@%s rbd -p %s ls 2>/dev/null| grep %s | grep %s" \
            % (g_user, g_host, g_remote_pool, image, postfix_image)
    rc, output = execute_cmd(cmd)
    if rc != 0:
        return True

    if len(output) > 0:
        return False
    else:
        return True

def has_local_snap(pool, image):
    cmd = "rbd -p %s snap ls %s" % (pool, image)
    rc, output = execute_cmd(cmd)
    if rc == 0 and len(output) >= 2:
        return True
    else:
        return False

def time_to_full_backup(pool, image):
    """
    if there are more than N snapshots or
    if it's weekend,
    then do full backup.
    """
    cmd = "rbd -p %s snap ls %s" % (pool, image)
    rc, output = execute_cmd(cmd)
    # remove the first line
    num_snaps = len(output) - 1
    today = datetime.datetime.today().weekday() 
    # 5/6 is Sat/Sun
    if num_snaps >= g_restart_every_n_days or today in [5, 6]:
        return True 
    else:
        return False
    pass


def find_most_recent_snap(pool, image):
    """
    example:
    [root@node-6 ~]# rbd -p rbd snap ls bkp_test_1
    SNAPID NAME                                    SIZE
        2 bkp_test_1_2015-06-17-07:39:02_snap 10240 MB
        3 bkp_test_1_2015-06-17-07:39:25_snap 10240 MB
        4 bkp_test_1_2015-06-17-07:39:37_snap 10240 MB
    """
    cmd = "rbd -p %s snap ls %s" % (pool, image)
    rc, output = execute_cmd(cmd)
    lastline = output[-1]
    snap = lastline.split()[1]
    return snap

def find_local_snaps(pool, image):
    cmd = "rbd -p %s snap ls %s" % (pool, image)
    rc, output = execute_cmd(cmd)
    if len(output) == 0:
        return []

    del output[0]
    out = map(lambda e:e.split()[1], output)
    return out

def find_remote_snaps(pool, image):
    cmd = "ssh %s@%s rbd -p %s snap ls %s 2>/dev/null" % (g_user, g_host, pool, image)
    rc, output = execute_cmd(cmd)
    if len(output) == 0:
        return []

    del output[0]
    out = map(lambda e:e.split()[1], output)
    return out

def find_most_recent_remote_image(image):
    cmd = "ssh %s@%s rbd -p %s ls 2>/dev/null| grep %s | grep .image" \
            % (g_user, g_host, g_remote_pool, image)
    rc, output = execute_cmd(cmd)
    if rc != 0:
        logging.debug("find_most_recent_remote_image failed.")
        return None

    if len(output) == 0:
        return None
    else:
        return output[-1]
        

def find_most_recent_full_backup(image):
    pass

def find_local_tmp_image(pool, image):
    cmd = "rbd -p %s ls | grep %s | grep .tmp" % (pool, image)
    rc, output = execute_cmd(cmd)
    if rc != 0 or len(output) == 0:
        logging.debug("No tmp image found.")
        return ""

    if len(output) > 1:
        logging.debug("WTF. There should be at most only one ONGOING restore operation.")
    return output[-1]

def create_snap(pool, image):
    snap = current + ".snap" 
    cmd = "rbd -p %s snap create --snap %s %s" % (pool, snap, image)
    rc, output = execute_cmd(cmd)
    return rc, snap

def create_remote_snap(image):
    snap = current + ".snap" 
    cmd = "ssh %s@%s rbd -p %s snap create --snap %s %s 2>/dev/null" \
            % (g_user, g_host, g_remote_pool, snap, image)
    rc, output = execute_cmd(cmd)
    return rc, snap
            
def create_remote_snap_if_not_exit(image, snap):
    cmd = "ssh %s@%s rbd -p %s snap create --snap %s %s 2>/dev/null" \
            % (g_user, g_host, g_remote_pool, snap, image)
    rc, output = execute_cmd(cmd)
    return rc

def build_target_image_mode_full(image):
    target_image = image + '.' + current + postfix_image
    return target_image

def build_snapname(pool, image, mode):
    if mode == "full":
        target_image = build_target_image_mode_full(image)
    else:
        target_image = find_most_recent_remote_image(image)

    snap = current + ".snap"

    full_snap = g_remote_pool + '/' + target_image + '@' + snap
    return full_snap

def mk_indication_dir_if_not_exist():
    if os.path.exists(g_async_indication_dir) == False:
        os.mkdir(g_async_indication_dir)
    elif os.path.isdir(g_async_indication_dir) == False:
        logging.debug("g_async_indication_dir exists but is not a directory.")
        sys.exit(-1)
    else:
        pass

    # check again to make sure the g_async_indication_dir is one directory
    if os.path.isdir(g_async_indication_dir):
        pass
    else:
        logging.debug("g_async_indication_dir exists but is not a directory.")
        sys.exit(-1)

def touchfile(path):
    with open(path, 'a'):
        os.utime(path, None)
    #TODO ensure file exist, may not necessary???

def trim_slash_in_snapname(tfn):
    def _trim_slash(snapname):
        snap = snapname.replace("/","-")
        return tfn(snap)
        pass
    return _trim_slash

@trim_slash_in_snapname
def touch_ongoing_file(snapname):
    mk_indication_dir_if_not_exist()
    ongoing_file = g_async_indication_dir + '/' + snapname + g_async_indication_ongoing
    touchfile(ongoing_file)

@trim_slash_in_snapname
def touch_done_file(snapname):
    mk_indication_dir_if_not_exist()
    done_file = g_async_indication_dir + '/' + snapname + g_async_indication_done
    touchfile(done_file)

@trim_slash_in_snapname
def touch_fail_file(snapname):
    mk_indication_dir_if_not_exist()
    fail_file = g_async_indication_dir + '/' + snapname + g_async_indication_fail
    touchfile(fail)

def is_file_exist(path):
    try:
        statinfo = os.stat(path)
        return True
    except OSError:
        return False

@trim_slash_in_snapname
def is_done(snapname):
    done_file = g_async_indication_dir + '/' + snapname + g_async_indication_done
    return is_file_exist(done_file)

    # Why below code doesn't work???
    if os.path.exists(done_file):
        return True
    else:
        return False

@trim_slash_in_snapname
def is_failed(snapname):
    fail_file = g_async_indication_dir + '/' + snapname + g_async_indication_fail
    return is_file_exist(fail_file)

    if os.path.exists(fail_file):
        return True
    else:
        return False

@trim_slash_in_snapname
def is_ongoing(snapname):
    ongoing_file = g_async_indication_dir + '/' + snapname + g_async_indication_ongoing
    return is_file_exist(ongoing_file)

@trim_slash_in_snapname
def cleanup_indication_file(snapname):
    ongoing_file = g_async_indication_dir + '/' + snapname + g_async_indication_ongoing
    done_file = g_async_indication_dir + '/' + snapname + g_async_indication_done
    fail_file = g_async_indication_dir + '/' + snapname + g_async_indication_fail

    # May fail as EONENT, ignore it.
    try:
        os.remove(ongoing_file)
    except OSError:
        pass

    try:
        os.remove(done_file)
    except OSError:
        pass

    try:
        os.remove(fail_file)
    except OSError:
        pass


# For full backup, the ETA should be the time of backup one image plus the
# time of removing one copy
# return rc, snapname
# snapname example:
#       remote_pool/remote_image@snapname
def backup_image(pool, image, mode):
    """
    If backing up to another ceph cluster, remote pool
    must exist. If not, need to manually create it first.
    TODO In future, might support backup to remote file system.
    """
    global current
    first_bkp = is_first_backup(pool, image)
    if first_bkp and mode != "full":
        logging.debug("backup_image: must do full backup for the first time.")
        #TODO change mode to "full"???
        return -1, ""

    snap = ""
    full_snap = ""
    target_image = ""
    if mode == "full":
        target_image = build_target_image_mode_full(image)
        rc, snap = create_snap(pool, image)
        if rc != 0:
            logging.debug("backup_image: create first snap failed, rc %d.", (rc))
            return -1, ""
        # example:
        # rbd -p rbd export bkp_test_1 - | ssh root@node-7 rbd import -
        # bkp_test_1 -p rbd-bkp
        #cmd = "rbd export-diff %s/%s@%s - 2>/dev/null| ssh %s@%s rbd import - %s -p %s 2>/dev/null" \
        cmd = "rbd export %s/%s@%s - 2>/dev/null | ssh %s@%s rbd import - %s -p %s 2>/dev/null" \
                % (pool, image, snap, g_user, g_host, target_image, g_remote_pool)
        rc, output = execute_cmd(cmd)
        logging.debug("backup_image: rc %d.", (rc))
        if rc != 0:
            logging.debug("backup_image: failed, rc %d.", (rc))
            return -1, ""

        rc, snap = create_remote_snap(target_image)
        if rc != 0:
            logging.debug("backup_image, failed to create snap.")
            return -1, ""
    elif mode == "incr":
        last_snap = find_most_recent_snap(pool, image)
        rc, snap = create_snap(pool, image)
        if rc != 0:
            logging.debug("backup_image, failed to create snap.")
            return -1, ""

        target_image = find_most_recent_remote_image(image)
        cmd = "rbd export-diff --from-snap %s %s/%s@%s - 2>/dev/null| ssh %s@%s rbd import-diff - %s/%s 2>/dev/null" \
                % (last_snap, pool, image, snap, g_user, g_host, g_remote_pool, target_image)
        rc, output = execute_cmd(cmd)
        logging.debug("backup_image: rc %d.", (rc))
        if rc != 0:
            logging.debug("backup_image: failed, rc %d.", (rc))
            return -1, ""
    elif mode == "delta":
        logging.debug("backup_image, delta mode is not supported yet.")
        return -1, ""
    else:
        logging.debug("backup_image: Unknown backup mode %s", (mode))
        return -1, ""

    logging.debug("backup_image: pool %s, image %s, mode %s.",
                    *(pool, image, mode))

    if mode == "full":
        cleanup_after_full_backup(image)

    full_snap = g_remote_pool + '/' + target_image + '@' + snap
    return rc, full_snap

def restore_from(pool, image):
    """
    return mode, remote_image
    """
    # currently mode is always "full".
    # TODO if we support backup to remote FS, then mode might be "incr" or
    # "delta"
    mode = "full"

    # if has local snapshot, we were doing "incr" last time, so recovering from
    # remote image with same name. If hasn't, then we were doing "full" backup,
    # need to find out the latest remote image.
    if has_local_snap(pool, image):
        remote = image
    else:
        remote = find_most_recent_remote_image(image)

    return mode, remote

def restore_image(pool, image, snapname):
    """
    User should specify a version to restore via snapname.
    By using a different \a image, we can restore a version to
    another image.
    """
    #mode, remote = restore_from(pool, image)
    tmp_image = image + '.' + current + postfix_tmp_image

    get_host_cmd = "hostname -s"
    rc, output = execute_cmd(get_host_cmd)
    localhost = output[0]

    #cmd = "ssh %s@%s rbd -p %s export %s - | ssh %s@%s rbd -p %s import - %s" \
    #        % (g_user, g_host, g_remote_pool, remote, g_user, localhost, pool, tmp_image)

    cmd = "ssh %s@%s rbd export %s - 2>/dev/null| ssh %s@%s rbd import - %s/%s 2>/dev/null" \
            % (g_user, g_host, snapname, g_user, localhost, pool, tmp_image)
    logging.debug("restore_image: g_remote_pool %s, remote_image %s.",
                    *(g_remote_pool, snapname))
    rc, output = execute_cmd(cmd)
    logging.debug("restore_image: import %s from %s as image %s in pool %s, rc %d",
                   *(snapname, g_host, tmp_image, pool, rc))
    if rc != 0:
        sys.exit(rc)

    cmd = "rbd -p %s snap purge %s >/dev/null 2>&1; rbd -p %s rm %s >/dev/null 2>&1" \
            % (pool, image, pool, image)
    # old image might already been deleted, so ignore rc
    rc, output = execute_cmd(cmd)
    # ignore checking rc as image may not exist

    cmd = "rbd mv %s/%s %s/%s" % (pool, tmp_image, pool, image)
    rc, output = execute_cmd(cmd)
    logging.debug("restore_image: rename image %s to %s, rc %d.",
                    *(tmp_image, image, rc))
    if rc != 0:
        logging.debug("failed to rename %s to %s.", *(tmp_image, image))
        sys.exit(rc)

    """
    # After restore, we need to create one more full backup image on remote to
    # hold all following incremental snapshots.
    # build a local snapshot
    rc1, snap = create_snap(pool, image)
    # build a new full backup on remote and then create one snapshot for it.
    target_image = image + '.' + current + postfix_image
    cmd = "ssh %s@%s rbd export %s - 2>/dev/null| rbd import - %s/%s" % (g_user, g_host,
            snapname, g_remote_pool, target_image)
    rc, output = execute_cmd(cmd)
    if rc != 0:
        logging.debug("failed to create full image after one successful restore.")
        sys.exit(rc)

    rc2, snap = create_remote_snap(target_image)
    if rc1 != 0 or rc2 != 0:
        logging.debug("failed to create snapshot, rc1 %d, rc2 %d.", *(rc1, rc2))
        sys.exit(1)
    """

    return rc

# search "double fork" to discover more
def asynchronize_exec(async_fun, op, pool, image, mode, snapname):
    rc = 0
    tmp = ""
    pid = os.fork()
    if pid == 0:
        os.setsid()
        pid = os.fork()
        if pid == 0:
            if op == "backup":
                rc, tmp = async_fun(pool, image, mode)
            else:
                rc = async_fun(pool, image, snapname)

            if rc != 0:
                touch_fail_file(snapname)
            else:
                touch_done_file(snapname)
        else:
            sys.exit(0)
    pass

def backup_image_async(pool, image, mode):
    rc = 0
    snapname = build_snapname(pool, image, mode)

    touch_ongoing_file(snapname)
    asynchronize_exec(backup_image, "backup", pool, image, mode, snapname)

    return rc, snapname

def restore_image_async(pool, image, snapname):
    rc = 0

    touch_ongoing_file(snapname)
    asynchronize_exec(restore_image, "restore", pool, image, None, snapname)

    return rc

def delete_backup_image(pool, image, snapname):
    rc = 0
    if not snapname:
        # deleting all backup images TODO
        logging.debug("Trying to delete all backups for image %s.", (image))
        return rc

    # delete snapname itself and its successors
    rpool = snapname.split('/')[0]
    tmp = snapname.split('/')[1]
    target_image = tmp.split('@')[0]
    snap = tmp.split('@')[1]
    cmd = "ssh %s@%s rbd -p %s snap ls %s 2>/dev/null" % (g_user, g_host, rpool, target_image)
    rc, output = execute_cmd(cmd)
    if rc != 0:
        logging.debug("failed to list snapshots for image %s.", (target_image))
        sys.exit(rc)

    del output[0]
    snaps = []
    num_snaps = len(output)
    for i in range(0, num_snaps):
        tmp_snap = output[i].split()[1]
        if tmp_snap >= snap:
            snaps.append(tmp_snap)

    num_snaps_left = num_snaps - len(snaps)
    for s in snaps:
        # delete remote snap
        tmp_snap = rpool + '/' + target_image + '@' + s
        cmd = "ssh %s@%s rbd snap rm %s 2>/dev/null" % (g_user, g_host, tmp_snap)
        rc, output = execute_cmd(cmd)
        if rc != 0:
            logging.debug("falied to remove snap %s.", (tmp_snap))
            sys.exit(rc)

        # delete local snap
        local_snap = pool + '/' + image + '@' + s
        cmd = "rbd snap rm %s 2>/dev/null" % (local_snap)
        rc, output = execute_cmd(cmd)
        if rc != 0:
            logging.debug("falied to remove snap %s.", (local_snap))
            sys.exit(rc)

    if num_snaps_left == 0:
        cmd = "ssh %s@%s rbd -p %s rm %s 2>/dev/null" % (g_user, g_host, rpool, target_image)
        rc, output = execute_cmd(cmd)
        if rc != 0:
            logging.debug("falied to remove image %s.", (target_image))
            sys.exit(rc)

    return rc

def delete_local_snaps(pool, image):
    rc = 0
    local_snap_list = find_local_snaps(pool, image)
    for ls in local_snap_list:
        local_snap = pool + '/' + image + '@' + ls
        cmd = "rbd snap rm %s 2>/dev/null" % (local_snap)
        rc, output = execute_cmd(cmd)
        if rc != 0:
            logging.debug("falied to remove snap %s.", (local_snap))
            sys.exit(rc)
    return rc

def dump_backup_chain(pool, image):
    cmd = "ssh %s@%s rbd -p %s ls 2>/dev/null| grep %s" % (g_user, g_host, g_remote_pool,
            image)
    rc, output = execute_cmd(cmd)
    if rc != 0:
        logging.debug("failed to find backup images for %s.", (image))
        sys.exit(rc)

    bkp_images = output
    for i in bkp_images:
        if i == bkp_images[-1]:
            type = active_branch_type
        else:
            type = passive_branch_type

        logging.debug("=== %s === %s", *(i, type))
        cmd = "ssh %s@%s rbd -p %s snap ls %s 2>/dev/null" \
                % (g_user, g_host, g_remote_pool, i)
        rc, output = execute_cmd(cmd)
        snaps = output
        if len(snaps) >= 2:
            del snaps[0]
            for s in snaps:
                logging.debug("------ %s", (s))

    return rc

def du_backup_chain(pool, image):
    cmd = "ssh %s@%s rbd -p %s ls 2>/dev/null| grep %s" % (g_user, g_host, g_remote_pool,
            image)
    rc, output = execute_cmd(cmd)
    if rc != 0:
        logging.debug("failed to find backup images for %s.", (image))
        sys.exit(rc)

    bkp_images = output
    total_bytes = 0 # in MBs
    for i in bkp_images:
        cmd = "ssh %s@%s rbd diff %s/%s 2>/dev/null | awk '{SUM += $2} END {print SUM/1024/1024}'" \
                % (g_user, g_host, g_remote_pool, i)
        rc, output = execute_cmd(cmd)
        bytes = 0
        if len(output) == 1:
            bytes_str = output[0]
            bytes = int(bytes_str.split('.')[0])
            total_bytes = total_bytes + bytes
        logging.debug("backup chain %s used %d MBs.", *(i, bytes))

    logging.debug("backup total disk usage %d MBs for %s/%s.", *(total_bytes, pool,
        image))
    print total_bytes

    return rc

def du_snap(pool, image, snapname):
    rp, ri, rs = split_snapname_v2(snapname)

    remote_snap_list = find_remote_snaps(rp, ri)
    if rs not in remote_snap_list:
        logging.debug("Can't find snap %s in remote %s/%s.", *(rs, rp, ri))
        sys.exit(1)

    parent = ""
    for tmp in remote_snap_list:
        if tmp == rs:
            break
        parent = tmp

    if parent == "":
        # i am the first
        cmd = "ssh %s@%s rbd diff %s/%s 2>/dev/null | awk '{SUM += $2} END {print SUM/1024/1024}'" \
                % (g_user, g_host, rp, ri)
    else:
        # i have a parent
        #from_snap = rp + '/' + ri + '@' + parent
        cmd = "ssh %s@%s rbd diff -p %s -i %s --snap %s --from-snap %s 2>/dev/null|awk '{SUM += $2} END {print SUM/1024/1024}'" \
                % (g_user, g_host, rp, ri, rs, parent)

    logging.debug("cmd is %s.", (cmd))
    rc, output = execute_cmd(cmd)
    bytes = 0
    if len(output) == 1:
        logging.debug("output is %s.", (output[0]))
        bytes_str = output[0]
        bytes = int(bytes_str.split('.')[0])

    print bytes
    return 0

def split_snapname(snapname):
    # snapname example:
    # rbd2/zhangzh.2015-09-24.10:04:40.298789.bkp.image@2015-09-24.10:04:40.298789.snap

    p = snapname.split('/')[0]
    i = snapname.split('/')[1]
    i = i.split('@')[0]
    return p, i

def split_snapname_v2(snapname):
    p = snapname.split('/')[0]
    tmpi = snapname.split('/')[1]
    i = tmpi.split('@')[0]
    s = tmpi.split('@')[1]
    return p, i, s

def find_rbd_prefix_from_info(output):
    prefix = ""
    for o in output:
        s = o.split(':')
        if "block_name_prefix" in s[0]:
            prefix = s[1]
            break

    return prefix

def find_rbd_parent_from_info(output):
    parent = ""
    for o in output:
        s = o.split(':')
        if "parent" in s[0]:
            parent = s[1]
            break

    return parent

# when querying number of objects for one image, don't forget it might be
# created by cloning one parent image.
def num_objs_of_local_image(pool, image):
    cmd = "rbd -p %s info %s" % (pool, image)
    rc, output = execute_cmd(cmd)
    if rc != 0:
        logging.debug("No image %s in pool %s, number of objects is 0.", *(image, pool))
        return 0

    pn = 0
    parent = find_rbd_parent_from_info(output)
    if parent != "":
        # parent example:
        # parent: images/ff3447ab-607e-4095-a426-3ed64d571ce0@snap
        p, i = split_snapname(parent)
        pn = num_objs_of_local_image(p, i)

    prefix = find_rbd_prefix_from_info(output)
    if prefix == "":
        logging.debug("failed to find rbd data prefix for image in pool.", *(i, p))
        sys.exit(2)
    cmd = "rados -p %s ls | grep %s | wc -l" % (pool, prefix)
    rc, output = execute_cmd(cmd)
    if rc != 0:
        logging.debug("failed to lookup objects for image.")
        sys.exit(rc)
    l = int(output[0])

    return pn + l

def num_objs_of_remote_image(snapname):
    # snapname example:
    # rbd2/zhangzh.2015-09-24.10:04:40.298789.bkp.image@2015-09-24.10:04:40.298789.snap
    p, i = split_snapname(snapname)

    prefix = ""
    cmd = "ssh %s@%s rbd -p %s info %s 2>/dev/null" % (g_user, g_host, p, i)
    rc, output = execute_cmd(cmd)
    if rc != 0:
        logging.debug("failed to find remote image %s in pool %s.", *(i, p))
        sys.exit(rc)

    prefix = find_rbd_prefix_from_info(output)
    if prefix == "":
        logging.debug("failed to find rbd data prefix for image in pool.", *(i, p))
        sys.exit(2)

    cmd = "ssh %s@%s \"rados -p %s ls  | grep %s | wc -l\" 2>/dev/null" \
            % (g_user, g_host, p, prefix)
    rc, output = execute_cmd(cmd)
    if rc != 0:
        logging.debug("find_most_recent_remote_image failed.")
        sys.exit(rc)

    l = int(output[0])
    return l

# Note: there is no progress exposed by RBD functionality(the stdout output in
# sync mode doesn't count as we need one API to query where we are now.). So we
# have to simulate it. The basic idea is Ceph will split the giant RBD image
# into many small objects with default size of 4MB. And we can count the number
# of objects for each image. Suppose those objects are evenly distributed(it
# should be), the percentage should be easily calculated by r/l in following
# function. For one real word image, the result should be pretty accurate. But
# for images that are just created, which means it's almost empty, the result
# might be misleading. Well, in fact, user shouldn't backup those empty images as
# it contains no data. So let's leave it for now.
def query_snap_progress(op, pool, image, snapname):
    """
    It will return one percentage number between [0, 100] to indicate where the
    backup/restore progress are.
    Return value of 100 means the operation has done successfully.
    Return value of -1 means the operation failed for somehow.
    Return value of -2 means the operation is unsupported for query_snap_progress.
    """
    # quick path, check failed/done indication first. If so, no need for following calculation.
    if is_ongoing(snapname) == False:
        return -1
    if is_failed(snapname):
        cleanup_indication_file(snapname)
        return -1
    if is_done(snapname):
        cleanup_indication_file(snapname)
        return 100

    if op == "restore":
        tmpimage = find_local_tmp_image(pool, image)
        l = num_objs_of_local_image(pool, tmpimage)
    else:
        l = num_objs_of_local_image(pool, image)
    r = num_objs_of_remote_image(snapname)
    if op == "backup":
        if l == 0:
            logging.debug("WTF. Backuping one empty image.")
            p = 0
        else:
            p = float(r)/float(l)
    elif op == "restore":
        if r == 0:
            logging.debug("WTF. Restoring from empty image.")
            p = 0
        else:
            p = float(l)/float(r)
    else:
        # we shouldn't be here as all requests have been sanity checked.
        logging.debug("Unsupported operation for query_snap_progress.")
        return -2

    p = int(p*100)
    if p >= 100:
        if p > 100:
            # Shouldn't be here. But if it happens, the only thing we can count
            # on is waiting done or fail flag in this or next queries.
            p = 100
            logging.debug("WTF. Copying more objects than expected!!!")

        if is_done(snapname):
            cleanup_indication_file(snapname)
        else:
            # almost done, hang in there.
            #
            # Just in case of the last object is created, but fail finally.
            # We need to maintain a consistent view with upper layer callers.
            # Or we may leave one corrupted image on remote side which is
            # definitely not wanted.
            p = 99

    # TODO might output current MB/s, ETA too, those can be calculated.
    return p

def sanity_check(op, mode, pool, image, snapname, async):
    if op not in ["backup", "restore", "delete", "dump", "du", "du_snap", "delete_local_snaps", "query_backup", "query_restore"]:
        logging.debug("invalid operation %s, should be [backup|restore|delete|dump|du]", (op))
        sys.exit(1)

    if op == "backup" and mode not in ["full", "incr", "delta"]:
        logging.debug("invalid mode %s, should be [full|incr|delta]")
        sys.exit(1)

    if op == "restore" and not snapname:
        logging.debug("Need to specify from which snapshot to restore.")
        sys.exit(1)

    # TODO might support backup pool in future
    if op in ["backup", "restore", "du"] and (not pool or not image):
        logging.debug("Need to specify pool/image.")
        sys.exit(1)

    if op in ["backup", "retore", "du"] and not g_remote_pool:
        logging.debug("Need to specify remote pool..")
        sys.exit(1)

    if g_full_backup_to_keep < 0:
        logging.debug("Invalid parameter for number of full copies to keep.""")
        sys.exit(1)

    if async:
        if op not in ["backup", "restore"]:
            logging.debug("Don't support operation %s in async mode.", (op))
            sys.exit(1)
        
if __name__ == '__main__':

    logging.basicConfig(format='%(asctime)s %(filename)s[line:%(lineno)d] %(levelname)s - %(message)s',
                        filename=g_log, level=logging.DEBUG)

    parser = OptionParser() 
    parser.add_option("-p", "--pool", action="store", 
                      dest="pool", 
                      help="pool name for backup") 
    parser.add_option("-i", "--image", action="store", 
                      dest="image", 
                      help="image name for backup") 
    parser.add_option("-m", "--mode", action="store",
                      dest="mode",
                      help="backup mode, [full|incr|delta]")
    parser.add_option("-o", "--op", action="store",
                      dest="op",
                      help="operation type, should be [backup|restore|delete|dump|du]")
    parser.add_option("-r", "--remote", action="store",
                      dest="remote_pool",
                      help="remote pool for backup")
    parser.add_option("-s", "--from-snap", action="store",
                      dest="from_snap",
                      help="remote snapshot for backup")
    parser.add_option("-n", "--number_of_copies_to_keep", action="store",
                      type="int", dest="number_of_copies",
                      help="Keep at most N full copies, 0 means no limitation")
    parser.add_option("-u", "--user", action="store",
                      dest="remote_user",
                      help="user on remote host, need to access $user@$host w/o password")
    parser.add_option("-d", "--destination-host", action="store",
                      dest="remote_host",
                      help="remote host IP, need to access $user@$host w/o password")
    parser.add_option("-a", "--async", action="store_true",
                      dest="async",
                      help="backup/restore/delete in async way")

    (options, args) = parser.parse_args() 

    pool = options.pool
    image = options.image
    mode = options.mode
    op = options.op
    g_remote_pool = options.remote_pool
    snapname = options.from_snap
    async = False

    if options.remote_user:
        g_user = options.remote_user

    if options.remote_host:
        g_host = options.remote_host

    if options.number_of_copies:
        g_full_backup_to_keep = options.number_of_copies

    if options.async:
        async = True

    sanity_check(op, mode, pool, image, snapname, async)
    logging.debug("%s pool %s image %s mode %s, begin at %s.",
                   *(op, pool, image, mode, current))

    if op == "backup":
        if async:
            rc, snapname = backup_image_async(pool, image, mode)
        else:
            rc, snapname = backup_image(pool, image, mode)
        if rc == 0:
            logging.debug("backup image %s as %s in host %s.", *(image,
                snapname, g_host))
            #logging.info("%s", (snapname))
	        # THE ONLY OUTPUT TO STDOUT
            print snapname
    elif op == "restore":
        if async:
            rc = restore_image_async(pool, image, snapname)
        else:
            rc = restore_image(pool, image, snapname)
    elif op == "delete":
        rc = delete_backup_image(pool, image, snapname)
    elif op == "delete_local_snaps":
        rc = delete_local_snaps(pool, image)
    elif op == "dump":
        rc = dump_backup_chain(pool, image)
    elif op == "du":
        rc = du_backup_chain(pool, image)
    elif op == "du_snap":
        rc = du_snap(pool, image, snapname)
    elif op == "query_backup":
        rc = query_snap_progress("backup", pool, image, snapname)
        print rc
    elif op == "query_restore":
        rc = query_snap_progress("restore", pool, image, snapname)
        print rc
    else:
        logging.debug("Invalid operation.")
        sys.exit(1)

    end_date = str(datetime.datetime.today().date())
    end_timestamp = str(datetime.datetime.today().time())
    end_current = end_date + '.' + end_timestamp
    logging.debug("%s pool %s image %s mode %s, rc %d, end at %s.",
                   *(op, pool, image, mode, rc, end_current))
