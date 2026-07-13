from django.contrib.auth import get_user_model
from django.test import SimpleTestCase

from .models import BusinessPerformanceEntry, InventoryItem
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


class InventoryFeatureTests(SimpleTestCase):
    def test_inventory_total_cost_and_monthly_expense_are_calculated_per_user(self):
        user = get_user_model().objects.create_user(username="owner", email="owner@example.com", password="password123")

        InventoryItem.objects.create(user=user, product="Shears", cost=120.0)
        InventoryItem.objects.create(user=user, product="Gel", cost=80.0)
        BusinessPerformanceEntry.objects.create(user=user, month="2026-07", expenses=250.0, outcome="Strong sales")

        self.assertEqual(InventoryItem.objects.filter(user=user).count(), 2)
        self.assertEqual(InventoryItem.objects.filter(user=user).aggregate(total_cost=models.Sum("cost"))["total_cost"], 200.0)
        self.assertEqual(BusinessPerformanceEntry.objects.filter(user=user, month="2026-07").first().expenses, 250.0)
