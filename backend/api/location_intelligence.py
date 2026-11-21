"""
JanSahayak - Smart Location Intelligence & Hotspot Mapping Service (Task 15)

Features:
1. Strict GPS Validation: Only complaints with valid latitude and longitude
   (-90 <= lat <= 90, -180 <= lng <= 180, lat != 0 or lng != 0) are treated as geolocated.
2. Address-only complaints are NEVER fabricated into GPS points.
3. Spatial Hotspot Detection using Haversine clustering with a configurable radius (e.g. 500 meters).
4. Explainable centroid aggregation: Computes the mean coordinates of grouped complaints,
   clearly marking them as approximate cluster centers.
5. No duplicate counting: Each complaint belongs to at most one hotspot cluster.
6. Privacy & PII protection: Strips citizen names, phone numbers, and private credentials.
   Only returns anonymized complaint summaries (tracking ID, title, category, department, status, date).
"""

import math
from typing import Dict, Any, List, Optional
from datetime import datetime
from django.utils import timezone
from django.db.models import Count, Q
from .models import Complaint, Department, ComplaintCategory, ComplaintStatus
from .analytics_insights import parse_iso_datetime

# Earth radius in kilometers for Haversine distance
EARTH_RADIUS_KM = 6371.0


def haversine_distance(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """
    Computes great-circle distance between two GPS coordinates in kilometers.
    """
    d_lat = math.radians(lat2 - lat1)
    d_lon = math.radians(lon2 - lon1)
    a = (math.sin(d_lat / 2) ** 2 +
         math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) *
         math.sin(d_lon / 2) ** 2)
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return EARTH_RADIUS_KM * c


def is_valid_coordinate(lat: Any, lng: Any) -> bool:
    """
    Validates that latitude and longitude are valid numeric floats within Earth bounds.
    Rejects (0.0, 0.0) placeholder Null Island coordinates.
    """
    if lat is None or lng is None:
        return False
    try:
        lat_f = float(lat)
        lng_f = float(lng)
        if not (-90.0 <= lat_f <= 90.0 and -180.0 <= lng_f <= 180.0):
            return False
        # Treat exact (0, 0) as invalid placeholder unless specifically needed
        if abs(lat_f) < 0.000001 and abs(lng_f) < 0.000001:
            return False
        return True
    except (ValueError, TypeError):
        return False


def detect_hotspots(
    geolocated_complaints: List[Dict[str, Any]],
    distance_threshold_km: float = 0.5,
    min_cluster_size: int = 2
) -> List[Dict[str, Any]]:
    """
    Groups geolocated complaints into spatial hotspots using single-linkage neighborhood clustering.
    
    Guarantees:
    - Every geolocated complaint is assigned to at most one cluster (no double counting).
    - Clusters must have >= min_cluster_size complaints.
    - Centroid is computed as the arithmetic mean of member coordinates.
    - Centroid coordinates are explicitly labeled as approximate cluster centers.
    """
    if not geolocated_complaints:
        return []

    visited = set()
    clusters = []

    for i, p1 in enumerate(geolocated_complaints):
        if i in visited:
            continue

        cluster_members = [p1]
        visited.add(i)

        for j, p2 in enumerate(geolocated_complaints):
            if j in visited:
                continue

            # Compare distance against cluster centroid or initial seed
            dist = haversine_distance(p1["latitude"], p1["longitude"], p2["latitude"], p2["longitude"])
            if dist <= distance_threshold_km:
                cluster_members.append(p2)
                visited.add(j)

        if len(cluster_members) >= min_cluster_size:
            avg_lat = sum(m["latitude"] for m in cluster_members) / len(cluster_members)
            avg_lng = sum(m["longitude"] for m in cluster_members) / len(cluster_members)

            # Categorize primary dominant issue in cluster
            cat_counts = {}
            for m in cluster_members:
                cat_name = m.get("category_name") or "General"
                cat_counts[cat_name] = cat_counts.get(cat_name, 0) + 1
            primary_category = max(cat_counts, key=cat_counts.get)

            clusters.append({
                "hotspot_id": f"HS-{len(clusters) + 1:03d}",
                "approximate_latitude": round(avg_lat, 6),
                "approximate_longitude": round(avg_lng, 6),
                "complaint_count": len(cluster_members),
                "radius_meters": int(distance_threshold_km * 1000),
                "primary_category": primary_category,
                "is_approximate_center": True,
                "complaint_ids": [m["id"] for m in cluster_members],
                "tracking_ids": [m["tracking_id"] for m in cluster_members],
                "category_breakdown": cat_counts
            })

    # Sort hotspots by complaint count descending
    clusters.sort(key=lambda x: x["complaint_count"], reverse=True)
    return clusters


def calculate_location_intelligence(
    date_from: Optional[datetime] = None,
    date_to: Optional[datetime] = None,
    category_id: Optional[int] = None,
    department_id: Optional[int] = None,
    status_filter: Optional[str] = None,
    hotspot_radius_km: float = 0.5
) -> Dict[str, Any]:
    """
    Main entry point for location intelligence.
    
    Filters complaints, segregates verified GPS records from address-only records,
    detects hotspots, and produces category/department geographic distributions.
    """
    qs = Complaint.objects.all().select_related('category', 'department')

    # Apply filters
    if date_from:
        qs = qs.filter(created_at__gte=date_from)
    if date_to:
        qs = qs.filter(created_at__lte=date_to)
    if category_id:
        qs = qs.filter(category_id=category_id)
    if department_id:
        qs = qs.filter(department_id=department_id)
    if status_filter:
        qs = qs.filter(status=status_filter)

    total_count = qs.count()

    geolocated_points = []
    without_gps_count = 0

    # Categorize geographic distribution
    category_geo_map = {}
    department_geo_map = {}

    for comp in qs:
        lat = comp.latitude
        lng = comp.longitude

        cat_name = comp.category.name if comp.category else "Uncategorized"
        dept_name = comp.department.name if comp.department else "Unassigned"

        if is_valid_coordinate(lat, lng):
            lat_f = float(lat)
            lng_f = float(lng)

            # Sanitize complaint for map: exclude citizen PII (names, phone numbers)
            marker_data = {
                "id": comp.id,
                "tracking_id": comp.tracking_id,
                "title": comp.title,
                "category_id": comp.category_id,
                "category_name": cat_name,
                "department_id": comp.department_id,
                "department_name": dept_name,
                "status": comp.status,
                "priority": comp.priority,
                "latitude": lat_f,
                "longitude": lng_f,
                "address_preview": comp.landmark or comp.address[:60] if comp.address else "Reported location",
                "created_at": comp.created_at.isoformat() if comp.created_at else None
            }
            geolocated_points.append(marker_data)

            # Aggregations for geolocated complaints
            category_geo_map[cat_name] = category_geo_map.get(cat_name, 0) + 1
            department_geo_map[dept_name] = department_geo_map.get(dept_name, 0) + 1
        else:
            without_gps_count += 1

    # Detect Hotspots from verified GPS coordinates only
    hotspots = detect_hotspots(
        geolocated_points,
        distance_threshold_km=hotspot_radius_km,
        min_cluster_size=2
    )

    # Compute bounding box & center coordinate if points exist
    center_lat = None
    center_lng = None
    bounding_box = None

    if geolocated_points:
        lats = [p["latitude"] for p in geolocated_points]
        lngs = [p["longitude"] for p in geolocated_points]
        center_lat = round(sum(lats) / len(lats), 6)
        center_lng = round(sum(lngs) / len(lngs), 6)
        bounding_box = {
            "min_lat": min(lats),
            "max_lat": max(lats),
            "min_lng": min(lngs),
            "max_lng": max(lngs),
        }

    # Format distributions as lists
    category_distribution = [
        {"name": k, "count": v, "percentage": round(v / len(geolocated_points) * 100, 1)}
        for k, v in sorted(category_geo_map.items(), key=lambda item: item[1], reverse=True)
    ]
    department_distribution = [
        {"name": k, "count": v, "percentage": round(v / len(geolocated_points) * 100, 1)}
        for k, v in sorted(department_geo_map.items(), key=lambda item: item[1], reverse=True)
    ]

    return {
        "summary": {
            "total_complaints": total_count,
            "geolocated_complaints_count": len(geolocated_points),
            "without_gps_count": without_gps_count,
            "geolocated_percentage": round(len(geolocated_points) / total_count * 100, 1) if total_count > 0 else 0.0,
            "hotspot_count": len(hotspots),
            "hotspot_radius_meters": int(hotspot_radius_km * 1000)
        },
        "map_center": {
            "latitude": center_lat,
            "longitude": center_lng
        } if center_lat is not None else None,
        "bounding_box": bounding_box,
        "hotspots": hotspots,
        "complaint_markers": geolocated_points,
        "category_geographic_distribution": category_distribution,
        "department_geographic_distribution": department_distribution,
        "filters_applied": {
            "date_from": date_from.isoformat() if date_from else None,
            "date_to": date_to.isoformat() if date_to else None,
            "category_id": category_id,
            "department_id": department_id,
            "status": status_filter
        }
    }

