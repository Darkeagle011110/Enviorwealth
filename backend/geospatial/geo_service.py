import logging
import asyncio
from typing import Dict, Any

from .gee_client import GEEClient
from .bhuvan_client import BhuvanClient
from .postgis_utils import PostGISClient
from api.admin_geospatial import _gee_config, _gee_valid

logger = logging.getLogger(__name__)

class GeoService:
    """
    Orchestrates the geospatial data fetching across all services.
    """
    
    async def get_all_geo_data(self, geojson_polygon: Dict[str, Any]) -> Dict[str, Any]:
        """
        Takes a GeoJSON polygon and fetches data from GEE, Bhuvan, and PostGIS concurrently.
        """
        if not _gee_config or not _gee_valid:
            gee_res = {"existing_tree_cover_pct": None, "recent_clearing": None}
            logger.warning("GEE not configured. Skipping tree cover stats.")
        else:
            gee = GEEClient(service_account_json=_gee_config)
            gee_task = asyncio.create_task(gee.get_tree_cover_stats(geojson_polygon))

        bhuvan_task = asyncio.create_task(bhuvan.get_land_classification(geojson_polygon))
        postgis_task = asyncio.create_task(postgis.check_one_overlap(geojson_polygon))
        
        tasks_to_await = [bhuvan_task, postgis_task]
        if _gee_config and _gee_valid:
            tasks_to_await.insert(0, gee_task)
            results = await asyncio.gather(*tasks_to_await)
            gee_res = results[0]
            bhuvan_res = results[1]
            postgis_res = results[2]
        else:
            results = await asyncio.gather(*tasks_to_await)
            bhuvan_res = results[0]
            postgis_res = results[1]
        
        # Combine the results into a single object that the Rules Engine can digest
        return {
            "existing_tree_cover_pct": gee_res["existing_tree_cover_pct"],
            "recent_clearing": gee_res["recent_clearing"],
            "is_recorded_forest": bhuvan_res["is_recorded_forest"],
            "is_wasteland": bhuvan_res["is_wasteland"],
            "intersects_one": postgis_res["intersects_one"],
            "one_overlap_pct": postgis_res["overlap_pct"]
        }

geo_service = GeoService()
