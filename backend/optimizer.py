import shapely
from shapely.affinity import rotate


spot_length = 5.0
spot_width = 2.5
road_width = 5.0
road_spacing = 15.0

angles = [0, 15, 30, 45, 60, 75, 90, 105, 120, 135, 150, 165]
offsets = [0.0, 3.0, 6.0, 9.0, 12.0]

def empty_results():
    return {
        "spots": [],
        "roads": [],
        "stats": {
            "spotCount": 0,
            "efficiency": 0.0,
            "basementArea": 0.0,
            "roadArea": 0.0
        }
    }

def optimize_layout(outline, blocked_zones, entrance):
    """
    Main layout generation placeholder.
    
    Inputs:
        outline: List of (x, y) tuples representing the basement perimeter.
        blocked_zones: List of Lists of (x, y) tuples representing the column/elevator zones.
        entrance: (x, y) tuple representing the entrance location.
        
    Outputs:
        dict: containing spots, roads, and layout stats.
    """
    # convert input px to meters (10px = 1m)
    outline_m = [(p[0] / 10.0, p[1] / 10.0) for p in outline]
    blocked_m = [[(p[0] / 10.0, p[1] / 10.0) for p in zone] for zone in blocked_zones]
    entrance_m = (entrance[0] / 10.0, entrance[1] / 10.0)

    if len(outline_m) < 3:
        return empty_results()
    
    try:
        outline_poly = shapely.Polygon(outline_m)
        if not outline_poly.is_valid:
            outline_poly = outline_poly.buffer(0)
    except Exception as e:
        return empty_results()
    
    blocked_polys = []
    for b in blocked_m:
        if len(b) >= 3:
            try:
                blocked_poly = shapely.Polygon(b)
                if (blocked_poly.is_valid):
                    blocked_polys.append(blocked_poly)
            except Exception as e:
                pass
    
    bp_union = shapely.unary_union(blocked_polys) if blocked_polys else shapely.Polygon()

    try:
        usable_poly = outline_poly.difference(bp_union)
    except Exception as e:
        usable_poly = outline_poly

    if usable_poly.is_empty or not usable_poly.is_valid:
        return empty_results()
    
    best_spots = []
    best_roads_geom = shapely.Polygon()
    best_angle = 0

    centroid = outline_poly.centroid
    entrance_pt = shapely.Point(entrance_m)

    for angle in angles:
        rotated_usable = rotate(usable_poly, -angle, origin=centroid)
        rotated_entrance = rotate(entrance_pt, -angle, origin=centroid)

        if rotated_usable.is_empty:
            continue

        min_x, min_y, max_x, max_y = rotated_usable.bounds
        ex = rotated_entrance.x
        vertical_road = shapely.box(ex - 2.5, min_y, ex + 2.5, max_y)

        for offset in offsets:
            horiz_roads = []
            y = min_y + offset
            while y < max_y:
                horiz_roads.append(shapely.box(min_x, y - 2.5, max_x, y + 2.5))
                y += road_spacing

            road_network_tmp = shapely.unary_union([vertical_road] + horiz_roads)
            road_network_all = road_network_tmp.intersection(rotated_usable)
            road_network_all = road_network_all.buffer(-2.4, cap_style=2, join_style=2) \
                                               .buffer(2.4, cap_style=2, join_style=2) \
                                               .intersection(rotated_usable)

            if road_network_all.is_empty:
                continue

            # Break the road network into individual connected component polygons
            if road_network_all.geom_type == 'Polygon':
                components = [road_network_all]
            elif road_network_all.geom_type == 'MultiPolygon':
                components = list(road_network_all.geoms)
            else:
                components = []
                if hasattr(road_network_all, 'geoms'):
                    for g in road_network_all.geoms:
                        if g.geom_type in ['Polygon', 'MultiPolygon']:
                            components.append(g)
                else:
                    components = [road_network_all]

            # Filter components: only keep roads connected to the entrance (distance < 0.1m)
            connected_components = [comp for comp in components if comp.distance(rotated_entrance) < 0.1]
            if not connected_components:
                continue

            road_network = shapely.unary_union(connected_components)

            placed_spots = []
            placed_spots_union = shapely.Polygon()

            for road in horiz_roads:
                ry = (road.bounds[1] + road.bounds[3]) / 2.0
                rows_y = [
                    (ry + 2.5, ry + 7.5), # above
                    (ry - 7.5, ry - 2.5)  # below
                ]

                for y_min, y_max in rows_y:
                    x = min_x
                    while x < max_x:
                        spot_candidate = shapely.box(x, y_min, x + spot_width, y_max)
                        if rotated_usable.contains(spot_candidate):
                            if spot_candidate.intersection(road_network_tmp).area < 0.01:
                                shared_edge_len = spot_candidate.intersection(road_network).length
                                if shared_edge_len >= 2.0:
                                    overlap = 0.0 if placed_spots_union.is_empty else spot_candidate.intersection(placed_spots_union).area
                                    if overlap < 0.01:
                                        placed_spots.append(spot_candidate)
                                        if placed_spots_union.is_empty:
                                            placed_spots_union = spot_candidate
                                        else:
                                            placed_spots_union = shapely.unary_union([placed_spots_union, spot_candidate])
                        x += spot_width

            if len(placed_spots) > len(best_spots):
                best_spots = placed_spots
                best_roads_geom = road_network
                best_angle = angle

    if not best_spots:
        return empty_results()
    final_spots_geom = [rotate(spot, best_angle, origin=centroid) for spot in best_spots]
    final_roads_geom = rotate(best_roads_geom, best_angle, origin=centroid)

    spots_output = []
    for spot in final_spots_geom:
        coords = list(spot.exterior.coords)[:4]
        spots_output.append([{"x": round(c[0] * 10, 1), "y": round(c[1] * 10, 1)} for c in coords])

    roads_output = []
    if not final_roads_geom.is_empty:
        if final_roads_geom.geom_type == 'Polygon':
            coords = list(final_roads_geom.exterior.coords)
            roads_output.append([{"x": round(c[0] * 10, 1), "y": round(c[1] * 10, 1)} for c in coords])
        elif final_roads_geom.geom_type == 'MultiPolygon':
            for poly in final_roads_geom.geoms:
                coords = list(poly.exterior.coords)
                roads_output.append([{"x": round(c[0] * 10, 1), "y": round(c[1] * 10, 1)} for c in coords])
                                

    basement_area = outline_poly.area
    road_area = final_roads_geom.area if not final_roads_geom.is_empty else 0.0
    spot_area = len(best_spots) * (spot_length * spot_width)  # each spot = 12.5 m^2
    efficiency = spot_area / basement_area if basement_area > 0 else 0.0

    return {
        "spots": spots_output,
        "roads": roads_output,
        "stats": {
            "spotCount": len(best_spots),
            "efficiency": round(efficiency, 3),
            "basementArea": round(basement_area, 1),
            "roadArea": round(road_area, 1)
        }
    }
