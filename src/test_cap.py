from capdecode import decode, encode, review
def test_zero(): assert decode("0000000000000000") == ([], [])
def test_net_bind(): assert decode("0000000000000400")[0] == ["CAP_NET_BIND_SERVICE"]
def test_roundtrip(): assert decode(encode("CAP_CHOWN", "CAP_KILL", "CAP_SYS_ADMIN"))[0] == ["CAP_CHOWN", "CAP_KILL", "CAP_SYS_ADMIN"]
def test_full_root_41_bits():
    names, unknown = decode("000001ffffffffff"); assert len(names) == 41 and unknown == []
def test_unknown_bit_reported(): assert decode("0000020000000000")[1] == [41]
def test_review_flags_dangerous():
    flagged, names = review(encode("CAP_NET_BIND_SERVICE", "CAP_SYS_ADMIN")); assert [n for n, _ in flagged] == ["CAP_SYS_ADMIN"]
