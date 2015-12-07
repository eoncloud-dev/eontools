SaltAPIClient
########################

介绍
_______________________
SaltAPIClient封装salt-api服务为一个个的python对象。使用时只需声明一个对象
并调用其方法即可。为了解决相应延迟问题，所有的API都提供了异步版本。

目前支持的对象有:

* EventsClient
* CommandsClient
* FilesClient
* JobsClient
* MinionClient
* PkgClient.py
* ServiceClient
* UserGroupClient

使用说明
________________________
1. salt_api_setting.py中包含有使用salt-api服务的基本设置，使用前需正确配置。

::

   SALT_API_URL = "https://10.6.14.212:8080"
   SALT_API_EAUTH = "pam"
   SALT_API_USER = "eonfabric"
   SALT_API_PASSWORD = "eonfabric"
   SALT_API_SSL = False
   SALT_API_ENV = "prod"

2. 声明所需要的对象并调用其方法.
   比如在 **node1** , **node2** 上添加用户 **fake_user** :

::

    zhangzh@base[~]$cat salt-api.py
    from salt_api_client import UserGroupClient
    my_client = UserGroupClient(endpoint = "https://10.6.14.212:8080",
                                user = "eonfabric",
                                password = "eonfabric")
    r = my_client.add_user(['eonfabric-cobbler-client2',
                            'eonfabric-cobbler-client4.local.lan'],
                           'fake_user')
    print r
    r = my_client.delete_user(['eonfabric-cobbler-client2',
                               'eonfabric-cobbler-client4.local.lan'],
                              'fake_user')
    print r
    zhangzh@base[~]$python salt-api.py
    {u'eonfabric-cobbler-client2': True, u'eonfabric-cobbler-client4.local.lan': True}
    {u'eonfabric-cobbler-client2': True, u'eonfabric-cobbler-client4.local.lan': True}

3. 使用异步操作
   在生成对象时可以传入 ``async=True`` 参数，该客户端对象发出的操作均为异步操作

::

    zhangzh@base[~]$cat salt-api-async.py
    from salt_api_client import UserGroupClient
    from salt_api_client import JobsClient
    my_client = UserGroupClient(endpoint = "https://10.6.14.212:8080",
                                user = "eonfabric",
                                password = "eonfabric",
                                async=True)
    job_client = JobsClient()
    r = my_client.add_user(['eonfabric-cobbler-client2',
                            'eonfabric-cobbler-client4.local.lan'],
                           'fake_user')
    print r
    job_client.wait(r)
    r = my_client.delete_user(['eonfabric-cobbler-client2',
                               'eonfabric-cobbler-client4.local.lan'],
                              'fake_user')
    print r
    job_client.wait(r)
    job_details = job_client.print_job(r)
    print job_details
    zhangzh@base[~]$python salt-api-async.py
    20151202133803013033
    20151202133803547667
    {u'20151202133803547667': {u'Function': u'user.delete', u'Result': {u'eonfabric-cobbler-client2': {u'return': True}, u'eonfabric-cobbler-client4.local.lan': {u'return': True}}, u'Target': [u'eonfabric-cobbler-client2', u'eonfabric-cobbler-client4.local.lan'], u'Target-type': u'list', u'Arguments': [u'fake_user', u'remove=Trueforce=True'], u'StartTime': u'2015, Dec 02 13:38:03.547667', u'Minions': [u'eonfabric-cobbler-client2', u'eonfabric-cobbler-client4.local.lan'], u'User': u'eonfabric'}}


接口说明
__________________________

参数说明
++++++++++++++++++++++++++

* minion_id

  主机名或主机名列表， 比如 ``'node1'`` 或者 ``['node1','node2','node3']`` 。
  ``'*'`` 表示所有salt minions。

返回值说明
++++++++++++++++++++++++++

* 所有API（list_events例外，其返回流）都返回一个list或者dict。
* 以 ``list_`` 开始的接口返回一个所列出对象的List。
* 非 ``list_`` 开始的接口均返回dict，包含一个或多个KV对，
  key为所操作minion的minion_id, value为其执行结果。

EventsClient
++++++++++++++++++++++++++
* list_events()

  监控Salt事件流

::

  from EventsClient import EventsClient
  my_client = EventsClient()
  ev_stream = my_client.list_event()

CommandsClient
++++++++++++++++++++++++++
* run
* run_async

在选定节点上执行特定操作。

::

  from CommandsClient import CommandsClient
  cmd_client = CommandsClient()
  cmd_client.run(tgt = ['node1', 'node2'],
                 args = ['whoami'])

FilesClient
++++++++++++++++++++++++++
* distribute(minion_id, src_url, dest_path)

  将以URL形式提供的文件分发到指定机器的特定目录
  src_url: 文件的URL链接
  dest_path: 存到到minion_id的目标路径

::

  from FilesClient import FilesClient
  file_client = FilesClient()
  file_client.distribute(['node1', 'node2'],
                         'http://192.168.122.2/test/salt-api_2015.5.3+ds-1trusty1_all.deb',
                         /tmp/my_salt_api.deb)

JobsClient
++++++++++++++++++++++++++
* list_jobs()

  列出所有的job
* list_active()

  列出所有正在运行的job
* print_job(jid)

  展示job详情
  jid: job id, 异步API的返回值。
* wait(jid)

  等待job结束
* kill(jid)

  主动结束某个job

::

  from JobsClient import JobsClient
  job_client = JobsClient()
  job_client.list_jobs()
  job_client.list_active()
  job_client.print_job(jid)
  job_client.wait(jid)
  job_client.kill(jid)

MinionClient
++++++++++++++++++++++++++
* list_minions()

  列出所有（包括up/down）的minion
* list_up_minions()

  列出所有up的minion
* list_down_minions()

  列出所有down的minion
* list_minions_with_details()

  列出所有up的minion及其详情
* minion_detail(minion_id)

  列出某些minion的详情
* minion_grain_item(minion_id, grain_key)

  返回minion的grain item信息
  grain_key: string 或者 '*' 返回所有grain items

PkgClient
++++++++++++++++++++++++++
* list_available_pkgs()

  EonFabric项目中需先准备好对应包的salt sls文件才能支持其安装/卸载等功能
* install(minion_id, pkg_name)
* uninstall(minion_id, pkg_name)

::

  from PkgClient imiport PkgClient
  pkg_client = PkgClient()
  pkg_client.list_available_pkgs()
  pkg_client.install(['node1','node2'], 'apache')
  pkg_client.uninstall('node2', 'apache')

ServiceClient
++++++++++++++++++++++++++
* start(minion_id, service_name)

  启动某个服务
* stop(minion_id, service_name)

  停止某个服务
* status(minion_id, service_name)

  获取服务状态
* restart(minion_id, service_name)

  重启某个服务
* reload(minion_id, service_name)

  reload某个服务
* avaiable(minion_id, service_name)

  查看某个服务是否可用
* get_all(minion_id)

  返回所有可用服务的列表

::

  from ServiceClient import ServiceClient
  service_client = ServiceClient()
  service_client.start(['node1', 'node2'], apache)
  service_client.status(['node1', 'node2'], apache)

UserGroupClient
++++++++++++++++++++++++++
* list_users(minion_id)

  列出所有用户
* list_user_groups(minion_id, user)

  列出某个用户所属的组,
  user: string
* add_user(minion_id, user)

  添加用户
* set_user_password(minion_id, user, password)

  设置用户密码
  user/password: string
* delete_user(minion_id, user)

  删除用户
* info_user(minion_id, user)

  获取用户信息
* append_user_to_group(minion_id, user, groups)

  将用户加入一个或多个组
  user: string
  groups: string or list of strings.
* delete_user_from_group(minion_id, user, groups)

  将用户从一个或多个组中删除
* add_group(minion_id, group)

  添加用户组
  group: string
* delete_group(minion_id, group)

  删除用户组
* info_group(minion_id, group)

  获取用户组信息
* list_groups(minion_id)

  列出所有用户组

