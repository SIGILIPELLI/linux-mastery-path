from layers import make_layer, apply_layers, image_size
def test_later_layer_overrides():
    l1 = make_layer({"etc/app.conf": b"v1"}); l2 = make_layer({"etc/app.conf": b"v2"})
    assert apply_layers([l1, l2]) == {"etc/app.conf": b"v2"}
def test_whiteout_hides_file():
    l1 = make_layer({"tmp/build.tar": b"x" * 1000, "app/bin": b"ok"}); l2 = make_layer(deletes=["tmp/build.tar"])
    assert apply_layers([l1, l2]) == {"app/bin": b"ok"}
def test_deleting_does_not_shrink_image():
    l1 = make_layer({"tmp/big.bin": b"x" * 200000}); l2 = make_layer(deletes=["tmp/big.bin"])
    assert image_size([l1, l2]) > image_size([l1])                                   # the big file still ships in layer 1
def test_same_layer_cleanup_does_shrink():
    wasteful = [make_layer({"tmp/big.bin": b"x" * 200000, "app/bin": b"ok"}), make_layer(deletes=["tmp/big.bin"])]
    cleaned = [make_layer({"app/bin": b"ok"})]                                        # download + delete happened inside one RUN: never stored
    assert apply_layers(cleaned) == apply_layers(wasteful) and image_size(cleaned) < image_size(wasteful) / 5
def test_opaque_directory():
    l1 = make_layer({"data/a": b"1", "data/b": b"2"}); l2 = make_layer({"data/.wh..wh..opq": b"", "data/c": b"3"})
    assert apply_layers([l1, l2]) == {"data/c": b"3"}
def test_whiteout_removes_directory_tree():
    l1 = make_layer({"var/cache/x": b"1", "var/cache/sub/y": b"2", "var/lib/z": b"3"}); l2 = make_layer(deletes=["var/cache"])
    assert apply_layers([l1, l2]) == {"var/lib/z": b"3"}
