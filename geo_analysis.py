
from shapely.geometry import Point, Polygon, MultiPolygon, GeometryCollection
from shapely.ops import unary_union
import geopandas as gpd

from country_config import METRIC_CRS

# ---------- helper functions ----------

def union_geom_to_gdf(geom, crs, buffer_m):
    """Helper: union-resultaat netjes naar een GDF met (Multi)Polygonen"""
    polys = []
    if isinstance(geom, (Polygon, MultiPolygon)):
        polys = [geom] if isinstance(geom, Polygon) else list(geom.geoms)
    elif isinstance(geom, GeometryCollection):
        for g in geom.geoms:
            if isinstance(g, Polygon):
                polys.append(g)
            elif isinstance(g, MultiPolygon):
                polys.extend(list(g.geoms))
    return gpd.GeoDataFrame({"buffer_m": [buffer_m]*len(polys)}, geometry=polys, crs=crs)

# ---------- main functions ----------
def get_bufferzones(gdf, radius):
    # 1) Zorg dat je CRS bekend is (punten in WGS84)
    if gdf.crs is None:
        gdf = gdf.set_crs(4326)
    
    # 2) Naar een metrische projectie (per land ingesteld) en buffers maken
    gdf_rd = gdf.to_crs(METRIC_CRS)
    gdf_rd["geometry"] = gdf_rd.geometry.buffer(radius)

    # Dissolve alle buffers naar één geometrie
    buffer_union = unary_union(gdf_rd["geometry"])

    # Stop deze multipolygon op in een GeoDataFrames (1 rij, 1 geometrie)
    gdf_bufferunion = gpd.GeoDataFrame(
        {"buffer_m": [radius]}, geometry=[buffer_union], crs=gdf_rd.crs
    ).to_crs(epsg=4326)

    return gdf_rd, gdf_bufferunion