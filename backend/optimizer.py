import shapely
import shapely.ops
from shapely.affinity import rotate

# Specifications (in meters)
SPOT_LENGTH = 5.0
SPOT_WIDTH = 2.5
ROAD_WIDTH = 5.0
ROAD_SPACING = 15.0

# Search configurations
SEARCH_ANGLES = [0.0, 90.0]
SEARCH_OFFSETS = [0.0, 3.0, 6.0, 9.0, 12.0]

# Math / geometry thresholds and constants
PX_TO_M_SCALE = 10.0
BUFFER_TOLERANCE = 0.1
AREA_TOLERANCE = 0.01
MIN_SHARED_EDGE_ADJACENCY = 2.0
MIN_ROAD_PIECE_AREA = 1.0
MIN_POLYGON_VERTICES = 3
MAX_ENTRANCE_DISTANCE = 5.0
SPLIT_EXTENSION = 10.0
ROUNDING_PRECISION = 1
EFFICIENCY_PRECISION = 3

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
    # convert input px to meters
    outline_m = [(p[0] / PX_TO_M_SCALE, p[1] / PX_TO_M_SCALE) for p in outline]
    blocked_m = [[(p[0] / PX_TO_M_SCALE, p[1] / PX_TO_M_SCALE) for p in zone] for zone in blocked_zones]
    entrance_m = (entrance[0] / PX_TO_M_SCALE, entrance[1] / PX_TO_M_SCALE)

    half_road = ROAD_WIDTH * 0.5
    buffer_val = half_road - BUFFER_TOLERANCE
    road_clearance = ROAD_WIDTH + 2.0 * SPOT_LENGTH + half_road

    if len(outline_m) < MIN_POLYGON_VERTICES:
        return empty_results()
    
    try:
        outline_poly = shapely.Polygon(outline_m)
        if not outline_poly.is_valid:
            outline_poly = outline_poly.buffer(0)
    except Exception as e:
        return empty_results()
    
    blocked_polys = []
    for b in blocked_m:
        if len(b) >= MIN_POLYGON_VERTICES:
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
    best_horiz_roads = []

    centroid = outline_poly.centroid
    entrance_pt = shapely.Point(entrance_m)
    has_blocked = len(blocked_polys) > 0

    for angle in SEARCH_ANGLES:
        rotated_usable = rotate(usable_poly, -angle, origin=centroid)
        rotated_entrance = rotate(entrance_pt, -angle, origin=centroid)
        rotated_outline = rotate(outline_poly, -angle, origin=centroid)

        if rotated_usable.is_empty:
            continue

        min_x, min_y, max_x, max_y = rotated_usable.bounds
        ex = rotated_entrance.x

        for offset in SEARCH_OFFSETS:
            horiz_roads = []
            if not has_blocked:
                y = min_y + offset
                while y < max_y:
                    horiz_roads.append(shapely.box(min_x, y - half_road, max_x, y + half_road))
                    y += ROAD_SPACING
            else:
                y = min_y + road_clearance + offset
                while y <= max_y - road_clearance:
                    horiz_roads.append(shapely.box(min_x, y - half_road, max_x, y + half_road))
                    y += ROAD_SPACING

            if not has_blocked:
                vertical_road = shapely.box(ex - half_road, min_y, ex + half_road, max_y)
                road_network_tmp = shapely.unary_union([vertical_road] + horiz_roads)
            else:
                margin_road_raw = rotated_outline.exterior.buffer(ROAD_WIDTH, join_style=2).intersection(rotated_outline)
                road_network_tmp = shapely.unary_union([margin_road_raw] + horiz_roads)

            road_network_all = road_network_tmp.intersection(rotated_usable)
            eroded = road_network_all.buffer(-buffer_val, cap_style=2, join_style=2)
            if eroded.is_empty:
                continue

            # Break the eroded road network into individual connected component polygons
            if eroded.geom_type == 'Polygon':
                eroded_components = [eroded]
            elif eroded.geom_type == 'MultiPolygon':
                eroded_components = list(eroded.geoms)
            else:
                eroded_components = []
                if hasattr(eroded, 'geoms'):
                    for g in eroded.geoms:
                        if g.geom_type in ['Polygon', 'MultiPolygon']:
                            eroded_components.append(g)
                else:
                    eroded_components = [eroded]

            if not eroded_components:
                continue

            # Find the component of the eroded road network that is closest to the entrance
            closest_comp = min(eroded_components, key=lambda c: c.distance(rotated_entrance))
            if closest_comp.distance(rotated_entrance) > MAX_ENTRANCE_DISTANCE:
                continue

            # Select components of clean, original road_network_all that intersect closest_comp.
            # This avoids distorting corners and creating pointy artifacts from erosion-dilation.
            original_components = []
            if road_network_all.geom_type == 'Polygon':
                original_components = [road_network_all]
            elif road_network_all.geom_type == 'MultiPolygon':
                original_components = list(road_network_all.geoms)
            elif road_network_all.geom_type == 'GeometryCollection':
                for g in road_network_all.geoms:
                    if g.geom_type == 'Polygon':
                        original_components.append(g)
                    elif g.geom_type == 'MultiPolygon':
                        original_components.extend(g.geoms)

            connected_original_components = [poly for poly in original_components if poly.intersects(closest_comp)]
            road_network = shapely.unary_union(connected_original_components) if connected_original_components else shapely.Polygon()

            road_for_adjacency = road_network

            placed_spots = []
            placed_spots_union = shapely.Polygon()

            def try_place(spot_candidate):
                nonlocal placed_spots_union
                if rotated_usable.contains(spot_candidate):
                    if spot_candidate.intersection(road_network_tmp).area < AREA_TOLERANCE:
                        shared_edge_len = spot_candidate.intersection(road_for_adjacency).length
                        if shared_edge_len >= MIN_SHARED_EDGE_ADJACENCY:
                            overlap = 0.0 if placed_spots_union.is_empty else spot_candidate.intersection(placed_spots_union).area
                            if overlap < AREA_TOLERANCE:
                                placed_spots.append(spot_candidate)
                                if placed_spots_union.is_empty:
                                    placed_spots_union = spot_candidate
                                else:
                                    placed_spots_union = shapely.unary_union([placed_spots_union, spot_candidate])

            if not has_blocked:
                # Case 1: rows from horizontal roads, spine-outward placement
                rows_y = []
                for road in horiz_roads:
                    ry = (road.bounds[1] + road.bounds[3]) / 2.0
                    rows_y.append((ry + half_road, ry + half_road + SPOT_LENGTH))
                    rows_y.append((ry - half_road - SPOT_LENGTH, ry - half_road))

                for y_min, y_max in rows_y:
                    # Right of spine
                    x = ex + half_road
                    while x < max_x:
                        try_place(shapely.box(x, y_min, x + SPOT_WIDTH, y_max))
                        x += SPOT_WIDTH
                    # Left of spine
                    x = ex - half_road - SPOT_WIDTH
                    while x >= min_x:
                        try_place(shapely.box(x, y_min, x + SPOT_WIDTH, y_max))
                        x -= SPOT_WIDTH
            else:
                # Case 2: phased spot placement around margin + horizontal roads
                min_x_out, min_y_out, max_x_out, max_y_out = rotated_outline.bounds

                # Phase 1: Perpendicular spots in rows above/below horizontal roads
                for road in horiz_roads:
                    ry = (road.bounds[1] + road.bounds[3]) / 2.0
                    for y_min, y_max in [(ry + half_road, ry + half_road + SPOT_LENGTH),
                                         (ry - half_road - SPOT_LENGTH, ry - half_road)]:
                        x = min_x_out
                        while x < max_x_out:
                            try_place(shapely.box(x, y_min, x + SPOT_WIDTH, y_max))
                            x += SPOT_WIDTH

                # Phase 2: Perpendicular spots adjacent to top/bottom margin roads
                # Row above bottom margin road
                y_min = min_y_out + ROAD_WIDTH
                y_max = min_y_out + ROAD_WIDTH + SPOT_LENGTH
                x = min_x_out
                while x < max_x_out:
                    try_place(shapely.box(x, y_min, x + SPOT_WIDTH, y_max))
                    x += SPOT_WIDTH
                # Row below top margin road
                y_min = max_y_out - ROAD_WIDTH - SPOT_LENGTH
                y_max = max_y_out - ROAD_WIDTH
                x = min_x_out
                while x < max_x_out:
                    try_place(shapely.box(x, y_min, x + SPOT_WIDTH, y_max))
                    x += SPOT_WIDTH

                # Phase 3: Parallel spots along left and right margin roads (vertical columns)
                # Left margin: spots are 5.0 wide (x) x 2.5 tall (y), placed at x = margin_end
                left_x = min_x_out + ROAD_WIDTH
                y = min_y_out
                while y < max_y_out:
                    try_place(shapely.box(left_x, y, left_x + SPOT_LENGTH, y + SPOT_WIDTH))
                    y += SPOT_WIDTH
                # Right margin: spots placed to the left of right margin road
                right_x = max_x_out - ROAD_WIDTH - SPOT_LENGTH
                y = min_y_out
                while y < max_y_out:
                    try_place(shapely.box(right_x, y, right_x + SPOT_LENGTH, y + SPOT_WIDTH))
                    y += SPOT_WIDTH

            if len(placed_spots) > len(best_spots):
                best_spots = placed_spots
                best_roads_geom = road_network
                best_angle = angle
                best_horiz_roads = horiz_roads

    if not best_spots:
        return empty_results()
    final_spots_geom = [rotate(spot, best_angle, origin=centroid) for spot in best_spots]

    # Split best_roads_geom to avoid holes in the SVG polygon rendering
    split_pieces = []
    if not best_roads_geom.is_empty:
        min_x, min_y, max_x, max_y = best_roads_geom.bounds
        lines = []
        for road in best_horiz_roads:
            y_min = road.bounds[1]
            y_max = road.bounds[3]
            lines.append(shapely.LineString([(min_x - SPLIT_EXTENSION, y_min), (max_x + SPLIT_EXTENSION, y_min)]))
            lines.append(shapely.LineString([(min_x - SPLIT_EXTENSION, y_max), (max_x + SPLIT_EXTENSION, y_max)]))
        
        if lines:
            splitter = shapely.MultiLineString(lines)
            try:
                split_geom = shapely.ops.split(best_roads_geom, splitter)
                for g in split_geom.geoms:
                    if g.geom_type == 'Polygon' and not g.is_empty and g.area > MIN_ROAD_PIECE_AREA:
                        split_pieces.append(g)
                    elif g.geom_type == 'MultiPolygon':
                        for subg in g.geoms:
                            if not subg.is_empty and subg.area > MIN_ROAD_PIECE_AREA:
                                split_pieces.append(subg)
            except Exception as e:
                # Fallback if split fails
                if best_roads_geom.geom_type == 'Polygon':
                    split_pieces.append(best_roads_geom)
                elif best_roads_geom.geom_type == 'MultiPolygon':
                    split_pieces.extend(best_roads_geom.geoms)
        else:
            if best_roads_geom.geom_type == 'Polygon':
                split_pieces.append(best_roads_geom)
            elif best_roads_geom.geom_type == 'MultiPolygon':
                split_pieces.extend(best_roads_geom.geoms)

    if split_pieces:
        final_roads_geom = rotate(shapely.MultiPolygon(split_pieces), best_angle, origin=centroid)
    else:
        final_roads_geom = shapely.Polygon()

    spots_output = []
    for spot in final_spots_geom:
        coords = list(spot.exterior.coords)[:4]
        spots_output.append([{"x": round(c[0] * PX_TO_M_SCALE, ROUNDING_PRECISION), "y": round(c[1] * PX_TO_M_SCALE, ROUNDING_PRECISION)} for c in coords])

    roads_output = []
    if not final_roads_geom.is_empty:
        if final_roads_geom.geom_type == 'Polygon':
            coords = list(final_roads_geom.exterior.coords)
            roads_output.append([{"x": round(c[0] * PX_TO_M_SCALE, ROUNDING_PRECISION), "y": round(c[1] * PX_TO_M_SCALE, ROUNDING_PRECISION)} for c in coords])
        elif final_roads_geom.geom_type == 'MultiPolygon':
            for poly in final_roads_geom.geoms:
                coords = list(poly.exterior.coords)
                roads_output.append([{"x": round(c[0] * PX_TO_M_SCALE, ROUNDING_PRECISION), "y": round(c[1] * PX_TO_M_SCALE, ROUNDING_PRECISION)} for c in coords])

    basement_area = outline_poly.area
    road_area = final_roads_geom.area if not final_roads_geom.is_empty else 0.0
    spot_area = len(best_spots) * (SPOT_LENGTH * SPOT_WIDTH)
    efficiency = spot_area / basement_area if basement_area > 0 else 0.0

    return {
        "spots": spots_output,
        "roads": roads_output,
        "stats": {
            "spotCount": len(best_spots),
            "efficiency": round(efficiency, EFFICIENCY_PRECISION),
            "basementArea": round(basement_area, ROUNDING_PRECISION),
            "roadArea": round(road_area, ROUNDING_PRECISION)
        }
    }
