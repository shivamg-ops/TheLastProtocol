"use client";

import { useEffect, useRef, useState } from "react";
import L from "leaflet";
import "leaflet/dist/leaflet.css";
import { MapPin, Flame, AlertCircle, Layers, ZoomIn, ZoomOut } from "lucide-react";

interface ComplaintMarker {
  id: number;
  tracking_id: string;
  title: string;
  category_id?: number;
  category_name?: string;
  department_id?: number;
  department_name?: string;
  status: string;
  priority: string;
  latitude: number;
  longitude: number;
  address_preview: string;
  created_at: string;
}

interface HotspotCluster {
  hotspot_id: string;
  approximate_latitude: number;
  approximate_longitude: number;
  complaint_count: number;
  radius_meters: number;
  primary_category: string;
  is_approximate_center: boolean;
  complaint_ids: number[];
  tracking_ids: string[];
}

interface LocationMapProps {
  markers: ComplaintMarker[];
  hotspots: HotspotCluster[];
  mapCenter: { latitude: number; longitude: number } | null;
  onSelectComplaint?: (complaint: ComplaintMarker) => void;
  onSelectHotspot?: (hotspot: HotspotCluster) => void;
}

export default function LocationIntelligenceMap({
  markers,
  hotspots,
  mapCenter,
  onSelectComplaint,
  onSelectHotspot,
}: LocationMapProps) {
  const mapContainerRef = useRef<HTMLDivElement>(null);
  const mapInstanceRef = useRef<L.Map | null>(null);
  const layerGroupRef = useRef<L.LayerGroup | null>(null);
  const [showHotspots, setShowHotspots] = useState(true);
  const [showMarkers, setShowMarkers] = useState(true);

  // Initialize Map Once
  useEffect(() => {
    if (!mapContainerRef.current) return;
    if (mapInstanceRef.current) return;

    const defaultLat = mapCenter?.latitude || 18.5204;
    const defaultLng = mapCenter?.longitude || 73.8567;

    const map = L.map(mapContainerRef.current, {
      center: [defaultLat, defaultLng],
      zoom: 12,
      zoomControl: false,
    });

    L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
      attribution:
        '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors',
      maxZoom: 19,
    }).addTo(map);

    L.control.zoom({ position: "bottomright" }).addTo(map);

    const layerGroup = L.layerGroup().addTo(map);
    layerGroupRef.current = layerGroup;
    mapInstanceRef.current = map;

    return () => {
      map.remove();
      mapInstanceRef.current = null;
    };
  }, []);

  // Update Markers and Hotspot Circles when data or filters change
  useEffect(() => {
    const map = mapInstanceRef.current;
    const layerGroup = layerGroupRef.current;
    if (!map || !layerGroup) return;

    layerGroup.clearLayers();

    const bounds = L.latLngBounds([]);

    // 1. Draw Hotspot Proximity Zones
    if (showHotspots) {
      hotspots.forEach((hs) => {
        bounds.extend([hs.approximate_latitude, hs.approximate_longitude]);

        // Semi-transparent buffer circle indicating cluster radius
        const circle = L.circle([hs.approximate_latitude, hs.approximate_longitude], {
          color: "#DC2626",
          fillColor: "#DC2626",
          fillOpacity: 0.18,
          radius: hs.radius_meters || 500,
          weight: 1.5,
          dashArray: "4, 4",
        });

        // Pulsing Hotspot Icon for Center
        const hotspotIcon = L.divIcon({
          className: "custom-hotspot-marker",
          html: `
            <div style="background-color: #DC2626; color: white; width: 32px; height: 32px; border-radius: 50%; display: flex; align-items: center; justify-content: center; font-weight: 800; font-size: 11px; border: 2.5px solid white; box-shadow: 0 4px 10px rgba(169, 77, 55, 0.45); cursor: pointer;">
              ${hs.complaint_count}
            </div>
          `,
          iconSize: [32, 32],
          iconAnchor: [16, 16],
        });

        const centerMarker = L.marker([hs.approximate_latitude, hs.approximate_longitude], {
          icon: hotspotIcon,
        });

        centerMarker.bindPopup(`
          <div style="font-family: inherit; font-size: 12px; line-height: 1.4;">
            <div style="font-weight: 700; color: #DC2626; margin-bottom: 2px;">
              🔥 Hotspot Cluster (${hs.hotspot_id})
            </div>
            <div style="font-size: 11px; color: #555; margin-bottom: 4px;">
              Approximate Cluster Center (${hs.radius_meters}m radius)
            </div>
            <div style="background: #f7f7f5; padding: 4px 6px; border-radius: 4px; margin-bottom: 4px;">
              <strong>Complaints:</strong> ${hs.complaint_count}<br/>
              <strong>Primary Issue:</strong> ${hs.primary_category}
            </div>
            <div style="font-size: 10px; color: #888;">
              Click to view clustered grievances
            </div>
          </div>
        `);

        centerMarker.on("click", () => {
          if (onSelectHotspot) onSelectHotspot(hs);
        });

        layerGroup.addLayer(circle);
        layerGroup.addLayer(centerMarker);
      });
    }

    // 2. Draw Verified Individual Complaint Pins
    if (showMarkers) {
      markers.forEach((m) => {
        bounds.extend([m.latitude, m.longitude]);

        // Status color coding
        let pinColor = "#3B82F6"; // default blue (submitted)
        if (m.status === "resolved" || m.status === "verified") pinColor = "#25845B";
        else if (m.status === "in_progress" || m.status === "assigned") pinColor = "#F59E0B";
        else if (m.status === "rejected") pinColor = "#EF4444";

        const pinIcon = L.divIcon({
          className: "custom-complaint-pin",
          html: `
            <div style="background-color: ${pinColor}; color: white; width: 18px; height: 18px; border-radius: 50%; border: 2px solid white; box-shadow: 0 2px 6px rgba(0,0,0,0.3); cursor: pointer;">
            </div>
          `,
          iconSize: [18, 18],
          iconAnchor: [9, 9],
        });

        const marker = L.marker([m.latitude, m.longitude], { icon: pinIcon });

        marker.bindPopup(`
          <div style="font-family: inherit; font-size: 12px; line-height: 1.4; max-width: 200px;">
            <div style="font-weight: 700; color: #17191D; font-family: monospace;">
              ${m.tracking_id}
            </div>
            <div style="font-weight: 600; color: #333; margin: 2px 0;">
              ${m.title}
            </div>
            <div style="font-size: 11px; color: #666; margin-bottom: 4px;">
              ${m.category_name || "General"} • <span style="text-transform: capitalize; font-weight: 600;">${m.status}</span>
            </div>
            <div style="font-size: 10px; color: #888; background: #fafafa; padding: 3px 5px; border-radius: 3px;">
              📍 ${m.address_preview}
            </div>
          </div>
        `);

        marker.on("click", () => {
          if (onSelectComplaint) onSelectComplaint(m);
        });

        layerGroup.addLayer(marker);
      });
    }

    // Auto-fit bounds if we have points
    if (bounds.isValid()) {
      map.fitBounds(bounds, { padding: [50, 50], maxZoom: 15 });
    } else if (mapCenter) {
      map.setView([mapCenter.latitude, mapCenter.longitude], 12);
    }
  }, [markers, hotspots, showHotspots, showMarkers, mapCenter]);

  return (
    <div className="relative w-full h-[500px] rounded-2xl overflow-hidden border border-gray-200 shadow-sm bg-[#F5F5F3]">
      <div ref={mapContainerRef} className="w-full h-full z-0" />

      {/* Map Layer Toggle Controls */}
      <div className="absolute top-3 right-3 z-10 bg-white/95 backdrop-blur-sm border border-gray-200/90 rounded-xl shadow-md p-2 flex flex-col gap-1.5 text-xs">
        <span className="text-[10px] font-bold text-gray-500 uppercase tracking-wider px-1">
          Map Layers
        </span>
        <button
          type="button"
          onClick={() => setShowHotspots(!showHotspots)}
          className={`flex items-center gap-1.5 px-2.5 py-1 rounded-lg text-xs font-semibold transition ${
            showHotspots
              ? "bg-[#DC2626] text-white shadow-xs"
              : "bg-gray-100 text-gray-600 hover:bg-gray-200"
          }`}
        >
          <Flame className="w-3.5 h-3.5" /> Hotspots ({hotspots.length})
        </button>
        <button
          type="button"
          onClick={() => setShowMarkers(!showMarkers)}
          className={`flex items-center gap-1.5 px-2.5 py-1 rounded-lg text-xs font-semibold transition ${
            showMarkers
              ? "bg-[#17191D] text-white shadow-xs"
              : "bg-gray-100 text-gray-600 hover:bg-gray-200"
          }`}
        >
          <MapPin className="w-3.5 h-3.5" /> Complaints ({markers.length})
        </button>
      </div>

      {/* Legend Overlay */}
      <div className="absolute bottom-3 left-3 z-10 bg-white/95 backdrop-blur-sm border border-gray-200/90 rounded-xl shadow-md px-3 py-2 text-[11px] text-gray-600 flex items-center gap-4">
        <div className="flex items-center gap-1.5">
          <span className="w-3 h-3 rounded-full bg-[#DC2626] inline-block border border-white shadow-xs"></span>
          <span>Hotspot Center</span>
        </div>
        <div className="flex items-center gap-1.5">
          <span className="w-2.5 h-2.5 rounded-full bg-blue-500 inline-block"></span>
          <span>Submitted</span>
        </div>
        <div className="flex items-center gap-1.5">
          <span className="w-2.5 h-2.5 rounded-full bg-amber-500 inline-block"></span>
          <span>In Field</span>
        </div>
        <div className="flex items-center gap-1.5">
          <span className="w-2.5 h-2.5 rounded-full bg-[#25845B] inline-block"></span>
          <span>Resolved</span>
        </div>
      </div>
    </div>
  );
}

