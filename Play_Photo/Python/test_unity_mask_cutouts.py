"""正式マスクからUnity用RGBA切り抜きを作る処理のモデル不要テスト。"""

from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

import cv2
import numpy as np

from udp_sender import build_payload
from unity_mask_cutouts import MaskCutoutSource, create_rgba_cutouts_from_masks


class UnityMaskCutoutTests(unittest.TestCase):
    def test_rgba_cutout_and_udp_payload_share_the_same_box(self) -> None:
        image = np.zeros((6, 8, 3), dtype=np.uint8)
        image[:, :] = (10, 80, 190)
        mask = np.zeros((6, 8), dtype=np.uint8)
        mask[2:5, 3:7] = 255

        with TemporaryDirectory() as temporary_dir:
            output_dir = Path(temporary_dir)
            stale = output_dir / "unity_object_old.png"
            unrelated = output_dir / "keep.png"
            stale.write_bytes(b"old")
            unrelated.write_bytes(b"keep")

            udp_objects, cutout_files = create_rgba_cutouts_from_masks(
                image,
                [MaskCutoutSource("test object", (3, 2, 6, 4), mask)],
                output_dir,
            )

            self.assertFalse(stale.exists())
            self.assertTrue(unrelated.exists())
            self.assertEqual(len(udp_objects), 1)
            self.assertEqual(udp_objects[0].box, (3, 2, 6, 4))
            self.assertEqual(cutout_files, ["unity_object_0001_test_object.png"])

            cutout = cv2.imread(
                str(output_dir / cutout_files[0]),
                cv2.IMREAD_UNCHANGED,
            )
            self.assertIsNotNone(cutout)
            self.assertEqual(cutout.shape, (3, 4, 4))
            self.assertTrue(np.all(cutout[:, :, 3] == 255))
            self.assertTrue(np.all(cutout[:, :, :3] == (10, 80, 190)))

            payload = build_payload(
                udp_objects,
                mode="legacy",
                cutout_files=cutout_files,
                image_width=8,
                image_height=6,
            )
            self.assertEqual(payload["imageWidth"], 8)
            self.assertEqual(payload["imageHeight"], 6)
            self.assertEqual(payload["objects"][0]["cutoutFileName"], cutout_files[0])
            self.assertEqual(payload["objects"][0]["x1"], 3.0)
            self.assertEqual(payload["objects"][0]["y4"], 4.0)

    def test_transparent_pixels_follow_the_mask(self) -> None:
        image = np.full((4, 4, 3), 120, dtype=np.uint8)
        mask = np.zeros((4, 4), dtype=np.uint8)
        mask[1, 1] = 255

        with TemporaryDirectory() as temporary_dir:
            _, filenames = create_rgba_cutouts_from_masks(
                image,
                [MaskCutoutSource("point", (0, 0, 2, 2), mask)],
                Path(temporary_dir),
            )
            cutout = cv2.imread(
                str(Path(temporary_dir) / filenames[0]),
                cv2.IMREAD_UNCHANGED,
            )
            self.assertEqual(int(cutout[1, 1, 3]), 255)
            self.assertEqual(int(cutout[0, 0, 3]), 0)

    def test_mismatched_mask_size_is_rejected(self) -> None:
        image = np.zeros((4, 4, 3), dtype=np.uint8)
        mask = np.zeros((3, 4), dtype=np.uint8)
        with TemporaryDirectory() as temporary_dir:
            with self.assertRaisesRegex(ValueError, "一致しません"):
                create_rgba_cutouts_from_masks(
                    image,
                    [MaskCutoutSource("bad", (0, 0, 2, 2), mask)],
                    Path(temporary_dir),
                )


if __name__ == "__main__":
    unittest.main(verbosity=2)
