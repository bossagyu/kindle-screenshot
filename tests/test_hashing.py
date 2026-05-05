from pathlib import Path
from PIL import Image
import pytest

from kindle_screenshot.hashing import compute_hash


def make_image(path: Path, color: tuple[int, int, int], size: tuple[int, int] = (200, 200)) -> Path:
    img = Image.new("RGB", size, color)
    img.save(path)
    return path


def test_compute_hash_same_image_same_hash(tmp_path):
    a = make_image(tmp_path / "a.png", (255, 0, 0))
    b = make_image(tmp_path / "b.png", (255, 0, 0))
    assert compute_hash(a) == compute_hash(b)


def test_compute_hash_different_images_different_hash(tmp_path):
    a = make_image(tmp_path / "a.png", (255, 0, 0))
    b = make_image(tmp_path / "b.png", (0, 0, 255))
    assert compute_hash(a) != compute_hash(b)


def test_compute_hash_returns_hex_string(tmp_path):
    a = make_image(tmp_path / "a.png", (128, 128, 128))
    h = compute_hash(a)
    assert isinstance(h, str)
    assert len(h) == 64
    int(h, 16)  # 16進文字列として有効


def test_compute_hash_is_stable_across_calls(tmp_path):
    """同じ画像を繰り返しハッシュしても同じ値が返る（リサンプリング明示の安定性確認 / L2）。

    リサンプリング方式が呼び出しごとにブレない（決定的）ことの間接検証。
    Pillow のデフォルト挙動が変わっても、本テストが破綻しない設計を担保する。
    """
    p = make_image(tmp_path / "a.png", (123, 45, 67), size=(800, 1200))
    hashes = [compute_hash(p) for _ in range(3)]
    assert hashes[0] == hashes[1] == hashes[2]


def test_compute_hash_independent_of_input_size_for_same_color(tmp_path):
    """同色の単色画像なら入力サイズに関わらずハッシュが一致する（縮小後は同じ
    64x64 グレースケールバイト列になるため）。リサンプリング方式が変わっても
    単色画像では結果が一定になることを確認する不変条件テスト。"""
    a = make_image(tmp_path / "a.png", (200, 100, 50), size=(400, 600))
    b = make_image(tmp_path / "b.png", (200, 100, 50), size=(800, 1200))
    assert compute_hash(a) == compute_hash(b)


from kindle_screenshot.hashing import DuplicateDetector


def test_detector_returns_false_for_first_hash():
    d = DuplicateDetector(stop_after=3)
    assert d.add("aaa") is False


def test_detector_returns_false_for_different_hashes():
    d = DuplicateDetector(stop_after=3)
    assert d.add("aaa") is False
    assert d.add("bbb") is False
    assert d.add("ccc") is False


def test_detector_returns_true_after_n_consecutive_duplicates():
    d = DuplicateDetector(stop_after=3)
    assert d.add("xxx") is False  # count=1
    assert d.add("xxx") is False  # count=2
    assert d.add("xxx") is True   # count=3, 停止


def test_detector_resets_counter_on_change():
    d = DuplicateDetector(stop_after=3)
    d.add("xxx")  # count=1
    d.add("xxx")  # count=2
    d.add("yyy")  # リセット, count=1
    assert d.add("yyy") is False  # count=2
    assert d.add("yyy") is True   # count=3


def test_detector_trim_count_after_trigger():
    d = DuplicateDetector(stop_after=3)
    d.add("a")    # count=1, trim=0
    d.add("a")    # count=2, trim=1
    d.add("a")    # count=3, trim=2 → 停止判定
    assert d.trim_count == 2


def test_detector_invalid_stop_after():
    with pytest.raises(ValueError):
        DuplicateDetector(stop_after=0)
