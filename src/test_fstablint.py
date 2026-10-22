from fstablint import lint
GOOD = """# <file system> <mount point> <type> <options> <dump> <pass>
UUID=11111111-2222-3333-4444-555555555555 /          ext4  errors=remount-ro        0 1
UUID=aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee /boot      ext4  defaults                 0 2
UUID=99999999-8888-7777-6666-555555555555 /data      xfs   defaults,nofail,noatime  0 0
UUID=cafecafe-cafe-cafe-cafe-cafecafecafe none       swap  sw                       0 0
tmpfs                                      /tmp       tmpfs defaults,noexec,nosuid,size=1g 0 0
nas:/export/backups                        /mnt/nas   nfs4  _netdev,nofail,ro        0 0
"""
def has(p, s): return any(s in x for x in p)
def test_good(): assert lint(GOOD) == []
def test_unstable_device_name(): assert has(lint(GOOD + "/dev/sdb1 /mnt/x ext4 defaults,nofail 0 2\n"), "unstable device name")
def test_nfs_without_netdev(): assert has(lint(GOOD + "nas:/e /mnt/e nfs defaults 0 0\n"), "_netdev")
def test_data_disk_without_nofail(): assert has(lint(GOOD + "UUID=12121212-1212-1212-1212-121212121212 /srv ext4 defaults 0 2\n"), "not marked nofail")
def test_root_pass(): assert has(lint(GOOD.replace("errors=remount-ro        0 1", "errors=remount-ro        0 2")), "fsck pass 1")
def test_xfs_pass(): assert has(lint(GOOD.replace("defaults,nofail,noatime  0 0", "defaults,nofail,noatime  0 2")), "xfs does not use fsck")
def test_tmp_hardening(): assert has(lint(GOOD.replace(",noexec,nosuid,size=1g", ",size=1g")), "noexec,nosuid")
def test_duplicate_mount(): assert has(lint(GOOD + "UUID=34343434-3434-3434-3434-343434343434 /data ext4 defaults,nofail 0 2\n"), "appears 2 times")
def test_too_few_fields(): assert has(lint("/dev/sda1 /mnt\n"), "at least 4 fields")
def test_comments_ignored(): assert lint("# nothing here\n\n") == []
