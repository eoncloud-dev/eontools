This tool is used to backup and restore rbd images. It also can calculate
total disk usage for one backup to support billing requirment.

Note::

   1. User need to do full backup first before incremental backup.
   2. User can query execution result by "echo $?"
   3. Backup operation will output one unique string as target backup id if succeed. User need to store it themselves as it's required in following restore operation.
   4. After restore, use need to do full backup next time.
   5. The du command will return disk usage in MBs.
   6. More options see "python rbd_backup.py -h".

Backup::

   [root@node-6 ~]# python rbd_backup.py -p rbd -i tmpimage -r rbd2 -u root -d node-7 -o backup -m full
   rbd2/tmpimage.2015-07-07.10:40:39.458883.bkp.image@2015-07-07.10:40:39.458883.snap
   [root@node-6 ~]# python rbd_backup.py -p rbd -i tmpimage -r rbd2 -u root -d node-7 -o backup -m incr
   rbd2/tmpimage.2015-07-07.10:40:39.458883.bkp.image@2015-07-07.10:40:43.707889.snap
   [root@node-6 ~]# echo $?
   0


Restore::

   # remove the source image just for testing.
   [root@node-6 ~]# rbd -p rbd snap purge tmpimage
   Removing all snapshots: 100% complete...done.
   [root@node-6 ~]# rbd -p rbd rm tmpimage
   Removing image: 100% complete...done.
   # real restore operation
   [root@node-6 ~]# python rbd_backup.py -p rbd -i tmpimage -r rbd2 -u root -d node-7 -o restore -s rbd2/tmpimage.2015-07-07.10:40:39.458883.bkp.image@2015-07-07.10:40:43.707889.snap
   [root@node-6 ~]# echo $?
   0
   # verification after restore
   [root@node-6 ~]# rbd -p info tmpimage
   rbd: error parsing command 'tmpimage'; -h or --help for usage
   [root@node-6 ~]# rbd -p rbd info tmpimage
   rbd image 'tmpimage':
         size 1024 MB in 256 objects
         order 22 (4096 kB objects)
         block_name_prefix: rb.0.cea1.238e1f29
         format: 1


Delete::

   [root@node-6 ~]# python rbd_backup.py -p rbd -i tmpimage -r rbd2 -u root -d node-7 -o delete -s rbd2/tmpimage.2015-07-07.10:51:27.252510.bkp.image@2015-07-07.10:51:33.461753.snap
   [root@node-6 ~]# echo $?
   0


Backup Chain, ONLY USED IN DEBUG MODE ::

   [root@node-6 ~]# python rbd_backup.py -p rbd -i tmpimage -r rbd2 -u root -d node-7 -o dump                                                                        
   2015-07-07 10:53:09,984 rbd_backup.py[line:503] DEBUG - dump pool rbd image tmpimage mode None, begin at 2015-07-07.10:53:09.983320.
   2015-07-07 10:53:10,083 rbd_backup.py[line:384] DEBUG - === tmpimage.2015-07-07.10:40:39.458883.bkp.image === passive
   2015-07-07 10:53:10,187 rbd_backup.py[line:392] DEBUG - ------     39 2015-07-07.10:40:39.458883.snap 58 bytes 
   2015-07-07 10:53:10,187 rbd_backup.py[line:392] DEBUG - ------     40 2015-07-07.10:40:43.707889.snap  1024 MB 
   2015-07-07 10:53:10,187 rbd_backup.py[line:384] DEBUG - === tmpimage.2015-07-07.10:43:49.347035.bkp.image === passive
   2015-07-07 10:53:10,286 rbd_backup.py[line:392] DEBUG - ------     41 2015-07-07.10:43:49.347035.snap 1024 MB 
   2015-07-07 10:53:10,287 rbd_backup.py[line:384] DEBUG - === tmpimage.2015-07-07.10:46:09.791281.bkp.image === passive
   2015-07-07 10:53:10,387 rbd_backup.py[line:392] DEBUG - ------     42 2015-07-07.10:46:09.791281.snap 1024 MB 
   2015-07-07 10:53:10,387 rbd_backup.py[line:384] DEBUG - === tmpimage.2015-07-07.10:51:27.252510.bkp.image === active
   2015-07-07 10:53:10,488 rbd_backup.py[line:392] DEBUG - ------     43 2015-07-07.10:51:27.252510.snap 4096 kB 
   2015-07-07 10:53:10,489 rbd_backup.py[line:529] DEBUG - dump pool rbd image tmpimage mode None, rc 0, end at 2015-07-07.10:53:10.489367.


Disk usage. The disk usage is returned in MBs. ::

   [root@node-6 ~]# python rbd_backup.py -p rbd -i tmpimage -r rbd2 -u root -d node-7 -o du
   13


Disk usage for one single backup operation. ::

   [root@node-6 ~]# rbd create zhangzh_tmp --size 10240
   [root@node-6 ~]# python eontools/rbd_backup.py -p rbd -i zhangzh_tmp -o backup -m full -r rbd2 -u root -d node-6
   rbd2/zhangzh_tmp.2015-10-08.09:52:36.239466.bkp.image@2015-10-08.09:52:36.239466.snap
   [root@node-6 ~]# python eontools/rbd_backup.py -p rbd -i zhangzh_tmp -o du_snap -s rbd2/zhangzh_tmp.2015-10-08.09:52:36.239466.bkp.image@2015-10-08.09:52:36.239466.snap -u root -d node-6
   0
   [root@node-6 ~]# python eontools/rbd_backup.py -p rbd -i zhangzh_tmp -o backup -m incr -r rbd2 -u root -d node-6                                                                         rbd2/zhangzh_tmp.2015-10-08.09:52:36.239466.bkp.image@2015-10-08.09:55:01.620737.snap
   [root@node-6 ~]# python eontools/rbd_backup.py -p rbd -i zhangzh_tmp -o du_snap -s rbd2/zhangzh_tmp.2015-10-08.09:52:36.239466.bkp.image@2015-10-08.09:55:01.620737.snap -u root -d node-6
   2868
   [root@node-6 ~]# python eontools/rbd_backup.py -p rbd -i zhangzh_tmp -o backup -m incr -r rbd2 -u root -d node-6                                                                         rbd2/zhangzh_tmp.2015-10-08.09:52:36.239466.bkp.image@2015-10-08.09:57:14.898665.snap
   [root@node-6 ~]# python eontools/rbd_backup.py -p rbd -i zhangzh_tmp -o du_snap -s rbd2/zhangzh_tmp.2015-10-08.09:52:36.239466.bkp.image@2015-10-08.09:57:14.898665.snap -u root -d node-6
   5692
   [root@node-6 ~]# python eontools/rbd_backup.py -p rbd -i zhangzh_tmp -o backup -m incr -r rbd2 -u root -d node-6                                                                         rbd2/zhangzh_tmp.2015-10-08.09:52:36.239466.bkp.image@2015-10-08.10:01:11.375287.snap
   [root@node-6 ~]# python eontools/rbd_backup.py -p rbd -i zhangzh_tmp -o du_snap -s rbd2/zhangzh_tmp.2015-10-08.09:52:36.239466.bkp.image@2015-10-08.10:01:11.375287.snap -u root -d node-6
   10240


Async mode support.
This tool supports async backup/restore now. Similar with sync mode, user
can add '-a' option to make it asynchronous. Besides, user can query backup
and restore progress by "query_backup" and "query_restore" command.
::

   [root@node-6 ~]# python eontools/rbd_backup.py -p compute -i e1287976-e9bf-4417-af76-b85fe8ae4a1c_disk -o backup -m full -r rbd -u root -d node-6 -a
   rbd/e1287976-e9bf-4417-af76-b85fe8ae4a1c_disk.2015-09-28.03:56:27.000863.bkp.image@2015-09-28.03:56:27.000863.snap
   [root@node-6 ~]# python eontools/rbd_backup.py -p compute -i e1287976-e9bf-4417-af76-b85fe8ae4a1c_disk -o query_backup -r rbd -u root -d node-6 -s rbd/e1287976-e9bf-4417-af76-b85fe8ae4a1c_disk.2015-09-28.03:56:27.000863.bkp.image@2015-09-28.03:56:27.000863.snap
   52
   [root@node-6 ~]# python eontools/rbd_backup.py -p compute -i e1287976-e9bf-4417-af76-b85fe8ae4a1c_disk -o query_backup -r rbd -u root -d node-6 -s rbd/e1287976-e9bf-4417-af76-b85fe8ae4a1c_disk.2015-09-28.03:56:27.000863.bkp.image@2015-09-28.03:56:27.000863.snap
   80
   [root@node-6 ~]# python eontools/rbd_backup.py -p compute -i e1287976-e9bf-4417-af76-b85fe8ae4a1c_disk -o query_backup -r rbd -u root -d node-6 -s rbd/e1287976-e9bf-4417-af76-b85fe8ae4a1c_disk.2015-09-28.03:56:27.000863.bkp.image@2015-09-28.03:56:27.000863.snap
   100


#restore::

   [root@node-6 ~]# python eontools/rbd_backup.py -p compute -i e1287976-e9bf-4417-af76-b85fe8ae4a1c_disk -o restore -r rbd -u root -d node-6 -s rbd/e1287976-e9bf-4417-af76-b85fe8ae4a1c_disk.2015-09-28.03:56:27.000863.bkp.image@2015-09-28.03:56:27.000863.snap -a
   [root@node-6 ~]# python eontools/rbd_backup.py -p compute -i e1287976-e9bf-4417-af76-b85fe8ae4a1c_disk -o query_restore -u root -d node-6 -s rbd/e1287976-e9bf-4417-af76-b85fe8ae4a1c_disk.2015-09-28.03:56:27.000863.bkp.image@2015-09-28.03:56:27.000863.snap
   99


TODO::

   1. Currently only support backup image to remote ceph cluster. Need to add support of backup to remote file system.
   2. Backup whole pool.

