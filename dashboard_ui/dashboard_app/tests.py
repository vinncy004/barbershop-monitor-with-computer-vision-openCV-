from django.test import SimpleTestCase

from .stream_processor import derive_detection_state


class StreamProcessorTests(SimpleTestCase):
    def test_detects_shaving_after_required_consecutive_frames(self):
        keypoints_list = [
            [
                [0.0, 0.0],
                [10.0, 10.0],
                [20.0, 20.0],
                [30.0, 30.0],
                [40.0, 40.0],
                [50.0, 50.0],
                [60.0, 60.0],
                [70.0, 70.0],
                [80.0, 80.0],
                [10.0, 10.0],
                [12.0, 12.0],
            ],
            [
                [100.0, 100.0],
                [110.0, 110.0],
                [120.0, 120.0],
            ],
        ]

        state, is_shaving, confidence, consecutive_frames = derive_detection_state(
            keypoints_list,
            consecutive_frames=4,
            proximity_threshold=150,
            required_frames=5,
        )

        self.assertEqual(state, "SHAVING ACTIVE")
        self.assertTrue(is_shaving)
        self.assertGreater(confidence, 0)
        self.assertEqual(consecutive_frames, 5)
