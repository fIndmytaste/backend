from types import SimpleNamespace
from unittest.mock import Mock, patch

from django.test import SimpleTestCase

from helpers.redis_geo import (
    GEO_INDEX_VALIDATION_KEY,
    GEO_KEY,
    _ensure_geo_index,
    _rebuild_geo_index,
)
from helpers.vendor_discovery import filter_and_sort_vendors_by_distance


class RedisGeoIndexRepairTests(SimpleTestCase):
    def _vendor(self, vendor_id="current-vendor"):
        return SimpleNamespace(
            id=vendor_id,
            location_latitude="6.5442935",
            location_longitude="3.4023064",
        )

    @patch("helpers.redis_geo._eligible_geo_vendors")
    def test_repairs_an_existing_but_incomplete_index(self, eligible_vendors):
        vendor = self._vendor()
        eligible_vendors.return_value = [vendor]

        redis_client = Mock()
        redis_client.exists.return_value = True
        redis_client.get.return_value = None
        redis_client.zrange.return_value = [b"stale-vendor"]
        pipe = redis_client.pipeline.return_value

        self.assertTrue(_ensure_geo_index(redis_client))

        pipe.delete.assert_called_once_with(GEO_KEY)
        pipe.execute_command.assert_called_once_with(
            "GEOADD",
            GEO_KEY,
            float(vendor.location_longitude),
            float(vendor.location_latitude),
            str(vendor.id),
        )
        pipe.execute.assert_called_once_with()
        redis_client.set.assert_called_once_with(
            GEO_INDEX_VALIDATION_KEY,
            "1",
            ex=5 * 60,
        )

    def test_rebuild_clears_stale_members_when_database_has_no_vendors(self):
        redis_client = Mock()
        pipe = redis_client.pipeline.return_value

        added = _rebuild_geo_index(redis_client, vendors=[])

        self.assertEqual(added, 0)
        pipe.delete.assert_called_once_with(GEO_KEY)
        pipe.execute.assert_called_once_with()


class VendorDiscoveryFallbackTests(SimpleTestCase):
    def _vendor(self, delivery_radius_km="10.00"):
        return SimpleNamespace(
            id="current-vendor",
            location_latitude="6.5442935",
            location_longitude="3.4023064",
            delivery_radius_km=delivery_radius_km,
            rating="3.00",
            name="Nearby vendor",
        )

    @patch(
        "helpers.vendor_discovery.get_distance_between_two_location",
        return_value=0.2,
    )
    @patch(
        "helpers.vendor_discovery.geo_nearby_vendor_ids",
        return_value=[("stale-vendor", 0.1)],
    )
    def test_stale_redis_ids_fall_back_to_database_distance(
        self,
        _geo_nearby_vendor_ids,
        _distance,
    ):
        vendor = self._vendor()

        results = filter_and_sort_vendors_by_distance(
            [vendor],
            6.5442935,
            3.4023064,
            enforce_delivery_radius=True,
        )

        self.assertEqual(results, [(vendor, 0.2)])

    @patch(
        "helpers.vendor_discovery.get_distance_between_two_location",
        return_value=12.0,
    )
    @patch("helpers.vendor_discovery.geo_nearby_vendor_ids", return_value=[])
    def test_fallback_keeps_the_same_browse_radius_as_redis(
        self,
        _geo_nearby_vendor_ids,
        _distance,
    ):
        vendor = self._vendor(delivery_radius_km="20.00")

        results = filter_and_sort_vendors_by_distance(
            [vendor],
            6.5442935,
            3.4023064,
            enforce_delivery_radius=True,
        )

        self.assertEqual(results, [])

    @patch(
        "helpers.vendor_discovery.get_distance_between_two_location",
        return_value=0.2,
    )
    @patch("helpers.vendor_discovery.geo_nearby_vendor_ids", return_value=[])
    def test_empty_redis_result_falls_back_to_database_distance(
        self,
        _geo_nearby_vendor_ids,
        _distance,
    ):
        vendor = self._vendor()

        results = filter_and_sort_vendors_by_distance(
            [vendor],
            6.5442935,
            3.4023064,
            enforce_delivery_radius=True,
        )

        self.assertEqual(results, [(vendor, 0.2)])
