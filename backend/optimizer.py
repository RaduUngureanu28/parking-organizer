import shapely
import shapely.ops
from shapely.affinity import rotate
import numpy as np

# Specifications (in meters)
SPOT_LENGTH = 5.0
SPOT_WIDTH = 2.5
ROAD_WIDTH = 5.0
ROAD_SPACING = 15.0

# Search configurations
SEARCH_OFFSETS = [0.0, 3.0, 6.0, 9.0, 12.0]

# Math / geometry thresholds and constants
PX_TO_M_SCALE = 10.0
AREA_TOLERANCE = 0.01
MIN_ROAD_PIECE_AREA = 1.0
MIN_POLYGON_VERTICES = 3
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

def calculate_spine_road_centers(short_len, offset):
    road_centers = []
    
    # Start at the offset, but clamp to the minimum physical road limit (2.5m)
    min_u = ROAD_WIDTH * 0.5
    u = max(offset, min_u)
    
    while u <= short_len - min_u:
        # Distance from the road edges to the boundaries
        dist_bottom = u - min_u
        dist_top = short_len - (u + min_u)
        
        # Valid if the gap is either flush (0) or big enough to fit a spot (>= 5.0m)
        bottom_ok = (dist_bottom < 0.1) or (dist_bottom >= SPOT_LENGTH - 0.1)
        top_ok = (dist_top < 0.1) or (dist_top >= SPOT_LENGTH - 0.1)
        
        if bottom_ok and top_ok:
            road_centers.append(u)
            
        u += ROAD_SPACING
        
    return road_centers



def generate_spine_roads(outline_poly, axes, road_centers, entrance_pt):
    origin = axes["origin"]
    short_dir = axes["short_dir"]
    long_dir = axes["long_dir"]
    long_len = axes["long_len"]
    short_len = axes["short_len"]
    
    # Project entrance_pt onto long_dir and clamp to avoid boundaries
    entrance_arr = np.array([entrance_pt.x, entrance_pt.y])
    t_entrance = np.dot(entrance_arr - origin, long_dir)
    half_rw = ROAD_WIDTH * 0.5
    t_entrance = max(half_rw, min(t_entrance, long_len - half_rw))
    
    roads = []
    
    # 1. Vertical Spine Road (aligned with short_dir, centered at t_entrance)
    half_rw = ROAD_WIDTH * 0.5
    t_min = t_entrance - half_rw
    t_max = t_entrance + half_rw
    
    spine_p0 = origin + t_min * long_dir
    spine_p1 = origin + t_max * long_dir
    spine_p2 = origin + t_max * long_dir + short_len * short_dir
    spine_p3 = origin + t_min * long_dir + short_len * short_dir
    
    spine_road = shapely.Polygon([spine_p0, spine_p1, spine_p2, spine_p3])
    clipped_spine = spine_road.intersection(outline_poly)
    if not clipped_spine.is_empty:
        if clipped_spine.geom_type == 'Polygon':
            roads.append(clipped_spine)
        elif clipped_spine.geom_type in ['MultiPolygon', 'GeometryCollection']:
            for g in clipped_spine.geoms:
                if g.geom_type == 'Polygon' and not g.is_empty:
                    roads.append(g)
                    
    # 2. Horizontal Roads (aligned with long_dir, centered at u)
    for u in road_centers:
        u_min = u - half_rw
        u_max = u + half_rw
        
        horiz_p0 = origin + u_min * short_dir
        horiz_p1 = origin + u_max * short_dir
        horiz_p2 = origin + u_max * short_dir + long_len * long_dir
        horiz_p3 = origin + u_min * short_dir + long_len * long_dir
        
        horiz_road = shapely.Polygon([horiz_p0, horiz_p1, horiz_p2, horiz_p3])
        clipped_horiz = horiz_road.intersection(outline_poly)
        if not clipped_horiz.is_empty:
            if clipped_horiz.geom_type == 'Polygon':
                roads.append(clipped_horiz)
            elif clipped_horiz.geom_type in ['MultiPolygon', 'GeometryCollection']:
                for g in clipped_horiz.geoms:
                    if g.geom_type == 'Polygon' and not g.is_empty:
                        roads.append(g)
                        
    return roads


def fill_leftover_spine_spots(outline_poly, all_roads_geom, axes, road_centers, entrance_pt, placed_spots_union):
    origin = axes["origin"]
    short_dir = axes["short_dir"]
    long_dir = axes["long_dir"]
    long_len = axes["long_len"]
    short_len = axes["short_len"]
    
    # Project entrance_pt onto long_dir and clamp to avoid boundaries
    entrance_arr = np.array([entrance_pt.x, entrance_pt.y])
    t_entrance = np.dot(entrance_arr - origin, long_dir)
    half_rw = ROAD_WIDTH * 0.5
    t_entrance = max(half_rw, min(t_entrance, long_len - half_rw))
    
    leftover_spots = []
    
    # 1. Sweep along the Vertical Spine (at t_entrance)
    u_step = 2.5
    u = 0.0
    while u <= short_len - SPOT_WIDTH:
        # Perpendicular candidates (width 2.5 along short_dir, length 5.0 along long_dir)
        perp_candidates = [
            # Right side
            (t_entrance + half_rw, t_entrance + half_rw + SPOT_LENGTH, u, u + SPOT_WIDTH),
            # Left side
            (t_entrance - half_rw - SPOT_LENGTH, t_entrance - half_rw, u, u + SPOT_WIDTH)
        ]
        
        # Parallel candidates (length 5.0 along short_dir, width 2.5 along long_dir)
        para_candidates = []
        if u <= short_len - SPOT_LENGTH:
            para_candidates = [
                # Right side
                (t_entrance + half_rw, t_entrance + half_rw + SPOT_WIDTH, u, u + SPOT_LENGTH),
                # Left side
                (t_entrance - half_rw - SPOT_WIDTH, t_entrance - half_rw, u, u + SPOT_LENGTH)
            ]
            
        for t_start, t_end, u_start, u_end in perp_candidates + para_candidates:
            p0 = origin + t_start * long_dir + u_start * short_dir
            p1 = origin + t_end * long_dir + u_start * short_dir
            p2 = origin + t_end * long_dir + u_end * short_dir
            p3 = origin + t_start * long_dir + u_end * short_dir
            
            spot_candidate = shapely.Polygon([p0, p1, p2, p3])
            
            if spot_candidate.difference(outline_poly).area < AREA_TOLERANCE:
                if spot_candidate.intersection(all_roads_geom).area < AREA_TOLERANCE:
                    if placed_spots_union.is_empty or spot_candidate.intersection(placed_spots_union).area < AREA_TOLERANCE:
                        leftover_spots.append(spot_candidate)
                        if placed_spots_union.is_empty:
                            placed_spots_union = spot_candidate
                        else:
                            placed_spots_union = shapely.unary_union([placed_spots_union, spot_candidate])
        u += u_step
        
    # 2. Sweep along all Horizontal Roads in road_centers
    t_step = 2.5
    for ry in road_centers:
        t = 0.0
        while t <= long_len - SPOT_WIDTH:
            # Perpendicular candidates (width 2.5 along long_dir, length 5.0 along short_dir)
            perp_candidates = [
                # Above
                (t, t + SPOT_WIDTH, ry + half_rw, ry + half_rw + SPOT_LENGTH),
                # Below
                (t, t + SPOT_WIDTH, ry - half_rw - SPOT_LENGTH, ry - half_rw)
            ]
            
            # Parallel candidates (length 5.0 along long_dir, width 2.5 along short_dir)
            para_candidates = []
            if t <= long_len - SPOT_LENGTH:
                para_candidates = [
                    # Above
                    (t, t + SPOT_LENGTH, ry + half_rw, ry + half_rw + SPOT_WIDTH),
                    # Below
                    (t, t + SPOT_LENGTH, ry - half_rw - SPOT_WIDTH, ry - half_rw)
                ]
                
            for t_start, t_end, u_start, u_end in perp_candidates + para_candidates:
                p0 = origin + t_start * long_dir + u_start * short_dir
                p1 = origin + t_end * long_dir + u_start * short_dir
                p2 = origin + t_end * long_dir + u_end * short_dir
                p3 = origin + t_start * long_dir + u_end * short_dir
                
                spot_candidate = shapely.Polygon([p0, p1, p2, p3])
                
                if spot_candidate.difference(outline_poly).area < AREA_TOLERANCE:
                    if spot_candidate.intersection(all_roads_geom).area < AREA_TOLERANCE:
                        if placed_spots_union.is_empty or spot_candidate.intersection(placed_spots_union).area < AREA_TOLERANCE:
                            leftover_spots.append(spot_candidate)
                            if placed_spots_union.is_empty:
                                placed_spots_union = spot_candidate
                            else:
                                placed_spots_union = shapely.unary_union([placed_spots_union, spot_candidate])
            t += t_step
            
    return leftover_spots, placed_spots_union


def place_spine_spots(outline_poly, all_roads_geom, axes, road_centers, entrance_pt):
    origin = axes["origin"]
    short_dir = axes["short_dir"]
    long_dir = axes["long_dir"]
    long_len = axes["long_len"]
    
    # Project entrance_pt onto long_dir and clamp to avoid boundaries
    entrance_arr = np.array([entrance_pt.x, entrance_pt.y])
    t_entrance = np.dot(entrance_arr - origin, long_dir)
    half_rw = ROAD_WIDTH * 0.5
    t_entrance = max(half_rw, min(t_entrance, long_len - half_rw))
    
    spots = []
    placed_spots_union = shapely.Polygon()
    
    for u in road_centers:
        row_bounds = [
            (u + half_rw, u + half_rw + SPOT_LENGTH),
            (u - half_rw - SPOT_LENGTH, u - half_rw)
        ]
        
        for u_start, u_end in row_bounds:
            # 1. Step to the right of the spine
            t = t_entrance + half_rw
            while t <= long_len - SPOT_WIDTH:
                p0 = origin + t * long_dir + u_start * short_dir
                p1 = origin + (t + SPOT_WIDTH) * long_dir + u_start * short_dir
                p2 = origin + (t + SPOT_WIDTH) * long_dir + u_end * short_dir
                p3 = origin + t * long_dir + u_end * short_dir
                
                spot_candidate = shapely.Polygon([p0, p1, p2, p3])
                
                if spot_candidate.difference(outline_poly).area < AREA_TOLERANCE:
                    if spot_candidate.intersection(all_roads_geom).area < AREA_TOLERANCE:
                        if placed_spots_union.is_empty or spot_candidate.intersection(placed_spots_union).area < AREA_TOLERANCE:
                            spots.append(spot_candidate)
                            if placed_spots_union.is_empty:
                                placed_spots_union = spot_candidate
                            else:
                                placed_spots_union = shapely.unary_union([placed_spots_union, spot_candidate])
                t += SPOT_WIDTH
                
            # 2. Step to the left of the spine
            t = t_entrance - half_rw - SPOT_WIDTH
            while t >= 0:
                p0 = origin + t * long_dir + u_start * short_dir
                p1 = origin + (t + SPOT_WIDTH) * long_dir + u_start * short_dir
                p2 = origin + (t + SPOT_WIDTH) * long_dir + u_end * short_dir
                p3 = origin + t * long_dir + u_end * short_dir
                
                spot_candidate = shapely.Polygon([p0, p1, p2, p3])
                
                if spot_candidate.difference(outline_poly).area < AREA_TOLERANCE:
                    if spot_candidate.intersection(all_roads_geom).area < AREA_TOLERANCE:
                        if placed_spots_union.is_empty or spot_candidate.intersection(placed_spots_union).area < AREA_TOLERANCE:
                            spots.append(spot_candidate)
                            if placed_spots_union.is_empty:
                                placed_spots_union = spot_candidate
                            else:
                                placed_spots_union = shapely.unary_union([placed_spots_union, spot_candidate])
                t -= SPOT_WIDTH
                
    leftover_spots, placed_spots_union = fill_leftover_spine_spots(
        outline_poly, all_roads_geom, axes, road_centers, entrance_pt, placed_spots_union
    )
    return spots + leftover_spots


def optimize_spine_layout(outline_poly, entrance_pt):
    axes = find_layout_axes(outline_poly)
    if not axes:
        return empty_results()
        
    best_spots = []
    best_roads = []
    
    for offset in SEARCH_OFFSETS:
        road_centers = calculate_spine_road_centers(axes["short_len"], offset)
        roads = generate_spine_roads(outline_poly, axes, road_centers, entrance_pt)
        all_roads_geom = shapely.unary_union(roads) if roads else shapely.Polygon()
        spots = place_spine_spots(outline_poly, all_roads_geom, axes, road_centers, entrance_pt)
        
        if len(spots) > len(best_spots):
            best_spots = spots
            best_roads = roads
            
    split_pieces = []
    for r in best_roads:
        split_pieces.extend(split_road_margins(r))
        
    roads_output = []
    for poly in split_pieces:
        coords = list(poly.exterior.coords)
        roads_output.append([{"x": round(c[0] * PX_TO_M_SCALE, ROUNDING_PRECISION), "y": round(c[1] * PX_TO_M_SCALE, ROUNDING_PRECISION)} for c in coords])

    spots_output = []
    for spot in best_spots:
        coords = list(spot.exterior.coords)[:4]
        spots_output.append([{"x": round(c[0] * PX_TO_M_SCALE, ROUNDING_PRECISION), "y": round(c[1] * PX_TO_M_SCALE, ROUNDING_PRECISION)} for c in coords])
        
    basement_area = outline_poly.area
    total_road_area = sum(r.area for r in best_roads)
    spot_area = len(best_spots) * (SPOT_LENGTH * SPOT_WIDTH)
    efficiency = spot_area / basement_area if basement_area > 0 else 0.0
    
    return {
        "spots": spots_output,
        "roads": roads_output,
        "stats": {
            "spotCount": len(best_spots),
            "efficiency": round(efficiency, EFFICIENCY_PRECISION),
            "basementArea": round(basement_area, ROUNDING_PRECISION),
            "roadArea": round(total_road_area, ROUNDING_PRECISION)
        }
    }

def find_layout_axes(poly):
    if poly.is_empty:
        return None
    min_rect = poly.minimum_rotated_rectangle
    rect_coords = list(min_rect.exterior.coords[:-1])
    if len(rect_coords) < 4:
        return None
    
    edge_vectors = []
    for i in range(len(rect_coords)):
        p1 = np.array(rect_coords[i])
        p2 = np.array(rect_coords[(i + 1) % len(rect_coords)])
        edge_vectors.append((p2 - p1, np.linalg.norm(p2 - p1)))
        
    v1, len1 = edge_vectors[0]
    v2, len2 = edge_vectors[1]
    
    if len1 == 0 or len2 == 0:
        return None
        
    if len1 >= len2:
        return {
            "origin": np.array(rect_coords[0]),
            "long_dir": v1 / len1,
            "short_dir": v2 / len2,
            "long_len": len1,
            "short_len": len2,
            "rect_coords": rect_coords
        }
    else:
        return {
            "origin": np.array(rect_coords[0]),
            "long_dir": v2 / len2,
            "short_dir": v1 / len1,
            "long_len": len2,
            "short_len": len1,
            "rect_coords": rect_coords
        }


def calculate_road_centers(short_len):
    road_centers = []
    u = SPOT_LENGTH
    while u <= short_len - (SPOT_LENGTH + ROAD_WIDTH * 0.5):
        road_centers.append(u)
        u += ROAD_WIDTH + 2 * SPOT_LENGTH
    return road_centers


def generate_interior_roads(inner_poly_outline, axes, road_centers):
    if not axes:
        return []
        
    origin = axes["origin"]
    short_dir = axes["short_dir"]
    long_dir = axes["long_dir"]
    long_len = axes["long_len"]
    
    interior_roads = []
    for u in road_centers:
        half_rw = ROAD_WIDTH * 0.5
        u_min = u - half_rw
        u_max = u + half_rw
        
        p0 = origin + u_min * short_dir
        p1 = origin + u_max * short_dir
        p2 = origin + u_max * short_dir + long_len * long_dir
        p3 = origin + u_min * short_dir + long_len * long_dir
        
        road_poly = shapely.Polygon([p0, p1, p2, p3])
        clipped_road = road_poly.intersection(inner_poly_outline)
        if not clipped_road.is_empty:
            if clipped_road.geom_type == 'Polygon':
                interior_roads.append(clipped_road)
            elif clipped_road.geom_type in ['MultiPolygon', 'GeometryCollection']:
                for g in clipped_road.geoms:
                    if g.geom_type == 'Polygon' and not g.is_empty:
                        interior_roads.append(g)
    return interior_roads


def place_interior_spots(inner_poly_outline, all_roads_geom, axes, road_centers):
    if not axes:
        return [], shapely.Polygon()
        
    origin = axes["origin"]
    short_dir = axes["short_dir"]
    long_dir = axes["long_dir"]
    long_len = axes["long_len"]
    
    interior_spots = []
    placed_spots_union = shapely.Polygon()
    
    for u in road_centers:
        t = 0.0
        while t <= long_len - SPOT_WIDTH:
            candidates = [
                (u + ROAD_WIDTH * 0.5, u + ROAD_WIDTH * 0.5 + SPOT_LENGTH),
                (u - ROAD_WIDTH * 0.5 - SPOT_LENGTH, u - ROAD_WIDTH * 0.5)
            ]
            
            for u_start, u_end in candidates:
                p0 = origin + t * long_dir + u_start * short_dir
                p1 = origin + (t + SPOT_WIDTH) * long_dir + u_start * short_dir
                p2 = origin + (t + SPOT_WIDTH) * long_dir + u_end * short_dir
                p3 = origin + t * long_dir + u_end * short_dir
                
                spot_candidate = shapely.Polygon([p0, p1, p2, p3])
                
                if spot_candidate.difference(inner_poly_outline).area < AREA_TOLERANCE:
                    if spot_candidate.intersection(all_roads_geom).area < AREA_TOLERANCE:
                        if placed_spots_union.is_empty or spot_candidate.intersection(placed_spots_union).area < AREA_TOLERANCE:
                            interior_spots.append(spot_candidate)
                            if placed_spots_union.is_empty:
                                placed_spots_union = spot_candidate
                            else:
                                placed_spots_union = shapely.unary_union([placed_spots_union, spot_candidate])
            t += SPOT_WIDTH
            
    return interior_spots, placed_spots_union


def place_margin_spots(inner_poly_outline, all_roads_geom, placed_spots_union):
    margin_spots = []
    
    islands = []
    if inner_poly_outline.geom_type == 'Polygon':
        islands.append(inner_poly_outline)
    elif inner_poly_outline.geom_type == 'MultiPolygon':
        islands.extend(inner_poly_outline.geoms)
        
    for island in islands:
        boundaries = [island.exterior] + list(island.interiors)
        for boundary in boundaries:
            coords = list(boundary.coords)
            for i in range(len(coords) - 1):
                A = np.array(coords[i])
                B = np.array(coords[i + 1])
                vec = B - A
                L = np.linalg.norm(vec)
                if L < SPOT_LENGTH:
                    continue
                
                d = vec / L
                p_vec = np.array([-d[1], d[0]])
                
                s = 0.0
                while s <= L - SPOT_LENGTH:
                    p0 = A + s * d
                    p1 = A + (s + SPOT_LENGTH) * d
                    
                    c0_A = p0
                    c1_A = p1
                    c2_A = p1 + SPOT_WIDTH * p_vec
                    c3_A = p0 + SPOT_WIDTH * p_vec
                    candidate_A = shapely.Polygon([c0_A, c1_A, c2_A, c3_A])
                    
                    c0_B = p0
                    c1_B = p1
                    c2_B = p1 - SPOT_WIDTH * p_vec
                    c3_B = p0 - SPOT_WIDTH * p_vec
                    candidate_B = shapely.Polygon([c0_B, c1_B, c2_B, c3_B])
                    
                    for candidate in [candidate_A, candidate_B]:
                        if candidate.difference(inner_poly_outline).area < AREA_TOLERANCE:
                            if candidate.intersection(all_roads_geom).area < AREA_TOLERANCE:
                                if placed_spots_union.is_empty or candidate.intersection(placed_spots_union).area < AREA_TOLERANCE:
                                    margin_spots.append(candidate)
                                    if placed_spots_union.is_empty:
                                        placed_spots_union = candidate
                                    else:
                                        placed_spots_union = shapely.unary_union([placed_spots_union, candidate])
                                    break
                    s += SPOT_LENGTH
                    
    return margin_spots


def split_road_margins(road_poly, grid_divisions=5):
    split_pieces = []
    if road_poly.is_empty:
        return split_pieces
        
    min_x, min_y, max_x, max_y = road_poly.bounds
    lines = []
    for i in range(1, grid_divisions):
        y = min_y + (max_y - min_y) * (i / float(grid_divisions))
        x = min_x + (max_x - min_x) * (i / float(grid_divisions))
        lines.append(shapely.LineString([(min_x - SPLIT_EXTENSION, y), (max_x + SPLIT_EXTENSION, y)]))
        lines.append(shapely.LineString([(x, min_y - SPLIT_EXTENSION), (x, max_y + SPLIT_EXTENSION)]))
    
    splitter = shapely.MultiLineString(lines)
    try:
        split_geom = shapely.ops.split(road_poly, splitter)
        for g in split_geom.geoms:
            if g.geom_type == 'Polygon' and not g.is_empty and g.area > MIN_ROAD_PIECE_AREA:
                split_pieces.append(g)
            elif g.geom_type == 'MultiPolygon':
                for subg in g.geoms:
                    if not subg.is_empty and subg.area > MIN_ROAD_PIECE_AREA:
                        split_pieces.append(subg)
    except Exception as e:
        if road_poly.geom_type == 'Polygon':
            split_pieces.append(road_poly)
        elif road_poly.geom_type == 'MultiPolygon':
            split_pieces.extend(road_poly.geoms)
            
    return split_pieces


def optimize_margin_layout(outline_poly, blocked_m, entrance_pt):
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
        
    # generate margins by buffering inwards
    inner_poly_outline = outline_poly.buffer(-ROAD_WIDTH)
    if inner_poly_outline.is_empty:
        return empty_results()
    if not inner_poly_outline.is_valid:
        inner_poly_outline = inner_poly_outline.buffer(0)
    
    road_poly = outline_poly.difference(inner_poly_outline)
    if not road_poly.is_valid:
        road_poly = road_poly.buffer(0)
    
    # Split road_poly to avoid holes in SVG rendering
    split_pieces = split_road_margins(road_poly)
    
    # Find layout axes and road centers
    axes = find_layout_axes(inner_poly_outline)
    if axes:
        road_centers = calculate_road_centers(axes["short_len"])
        
        # Phase 1: Generate interior roads and perpendicular spots
        interior_roads = generate_interior_roads(inner_poly_outline, axes, road_centers)
        split_pieces.extend(interior_roads)
        
        all_roads_geom = shapely.unary_union([road_poly] + interior_roads)
        interior_spots, placed_spots_union = place_interior_spots(inner_poly_outline, all_roads_geom, axes, road_centers)
        
        # Phase 2: Generate parallel spots along margins
        margin_spots = place_margin_spots(inner_poly_outline, all_roads_geom, placed_spots_union)
        total_spots = interior_spots + margin_spots
    else:
        interior_roads = []
        total_spots = []
        
    # Convert split_pieces back to coords for output (scale back to PX)
    roads_output = []
    for poly in split_pieces:
        coords = list(poly.exterior.coords)
        roads_output.append([{"x": round(c[0] * PX_TO_M_SCALE, ROUNDING_PRECISION), "y": round(c[1] * PX_TO_M_SCALE, ROUNDING_PRECISION)} for c in coords])

    # Convert total_spots back to coords for output (scale back to PX)
    spots_output = []
    for spot in total_spots:
        coords = list(spot.exterior.coords)[:4]
        spots_output.append([{"x": round(c[0] * PX_TO_M_SCALE, ROUNDING_PRECISION), "y": round(c[1] * PX_TO_M_SCALE, ROUNDING_PRECISION)} for c in coords])
                
    basement_area = outline_poly.area
    total_road_area = road_poly.area + sum(r.area for r in interior_roads)
    spot_area = len(total_spots) * (SPOT_LENGTH * SPOT_WIDTH)
    efficiency = spot_area / basement_area if basement_area > 0 else 0.0
    
    return {
        "spots": spots_output,
        "roads": roads_output,
        "stats": {
            "spotCount": len(total_spots),
            "efficiency": round(efficiency, EFFICIENCY_PRECISION),
            "basementArea": round(basement_area, ROUNDING_PRECISION),
            "roadArea": round(total_road_area, ROUNDING_PRECISION)
        }
    }


def optimize_layout(outline, blocked_zones, entrance):
    # convert input px to meters
    outline_m = [(p[0] / PX_TO_M_SCALE, p[1] / PX_TO_M_SCALE) for p in outline]
    blocked_m = [[(p[0] / PX_TO_M_SCALE, p[1] / PX_TO_M_SCALE) for p in zone] for zone in blocked_zones]
    entrance_m = (entrance[0] / PX_TO_M_SCALE, entrance[1] / PX_TO_M_SCALE)

    if len(outline_m) < MIN_POLYGON_VERTICES:
        return {"error": "Outline must have at least 3 vertices."}
    
    try:
        outline_poly = shapely.Polygon(outline_m)
        if not outline_poly.is_valid:
            outline_poly = outline_poly.buffer(0)
        if outline_poly.is_empty:
            return {"error": "Invalid self-intersecting or empty outline polygon. Please adjust the outline shape."}
    except Exception as e:
        return {"error": f"Failed to construct outline polygon: {str(e)}"}
        
    entrance_pt = shapely.Point(entrance_m)

    if len(blocked_zones) > 0:
        return optimize_margin_layout(outline_poly, blocked_m, entrance_pt)
    else:
        return optimize_spine_layout(outline_poly, entrance_pt)