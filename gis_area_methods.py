    # ── Area / % overlap (pure Python, no shapely — Sutherland-Hodgman clip
    #    of each candidate polygon against the project's rectangle, then
    #    shoelace-formula area). Re-run automatically every workbook reload
    #    since it's called from DataLoader._parse_row per record. ─────────

    @staticmethod
    def _clip_poly_rect(ring, xmin, ymin, xmax, ymax):
        """Sutherland-Hodgman: clip a (lon,lat) ring to an axis-aligned
        rectangle. Returns the clipped ring (possibly empty)."""
        def clip(points, inside, intersect):
            if not points:
                return []
            out = []
            n = len(points)
            for i in range(n):
                cur, prev = points[i], points[i - 1]
                cur_in, prev_in = inside(cur), inside(prev)
                if cur_in:
                    if not prev_in:
                        out.append(intersect(prev, cur))
                    out.append(cur)
                elif prev_in:
                    out.append(intersect(prev, cur))
            return out

        def isect_x(p1, p2, xb):
            x1, y1 = p1; x2, y2 = p2
            t = (xb - x1) / (x2 - x1)
            return (xb, y1 + t * (y2 - y1))

        def isect_y(p1, p2, yb):
            x1, y1 = p1; x2, y2 = p2
            t = (yb - y1) / (y2 - y1)
            return (x1 + t * (x2 - x1), yb)

        pts = list(ring)
        pts = clip(pts, lambda p: p[0] >= xmin, lambda a, b: isect_x(a, b, xmin))
        pts = clip(pts, lambda p: p[0] <= xmax, lambda a, b: isect_x(a, b, xmax))
        pts = clip(pts, lambda p: p[1] >= ymin, lambda a, b: isect_y(a, b, ymin))
        pts = clip(pts, lambda p: p[1] <= ymax, lambda a, b: isect_y(a, b, ymax))
        return pts

    @staticmethod
    def _shoelace_area(ring):
        if len(ring) < 3:
            return 0.0
        area = 0.0
        n = len(ring)
        for i in range(n):
            x1, y1 = ring[i]
            x2, y2 = ring[(i + 1) % n]
            area += x1 * y2 - x2 * y1
        return abs(area) / 2.0

    @classmethod
    def _polygon_area_in_bbox(cls, polygons, xmin, ymin, xmax, ymax):
        """Net area (exterior minus holes) of a feature's polygons that
        falls inside the given rectangle."""
        total = 0.0
        for poly in polygons:
            if not poly:
                continue
            exterior, holes = poly[0], poly[1:]
            clipped_ext = cls._clip_poly_rect(exterior, xmin, ymin, xmax, ymax)
            ext_area = cls._shoelace_area(clipped_ext)
            hole_area = 0.0
            for hole in holes:
                clipped_hole = cls._clip_poly_rect(hole, xmin, ymin, xmax, ymax)
                hole_area += cls._shoelace_area(clipped_hole)
            total += max(0.0, ext_area - hole_area)
        return total

    def bbox_overlap_pct(self, bbox):
        """bbox: [lat1, lat2, lon1, lon2] (as stored on each record, WGS-84
        — see the coordinate_transform note in the accompanying patch notes).
        Returns dict with province_pct / district_pct / local_pct /
        protected_pct / claimed_pct — each {name: percent_of_bbox_area}."""
        if not bbox or None in bbox:
            return {}
        lat1, lat2, lon1, lon2 = bbox
        ymin, ymax = sorted([lat1, lat2])
        xmin, xmax = sorted([lon1, lon2])
        eps = 0.0005  # guard against a degenerate (point) box
        if ymax - ymin < eps: ymax = ymin + eps
        if xmax - xmin < eps: xmax = xmin + eps
        total_area = (xmax - xmin) * (ymax - ymin)
        if total_area <= 0:
            return {}

        def _pct_for(items):
            out = {}
            for name, polygons, ibbox in items:
                if ibbox:
                    ilon_min, ilon_max, ilat_min, ilat_max = ibbox
                    if ilon_max < xmin or ilon_min > xmax or ilat_max < ymin or ilat_min > ymax:
                        continue  # cheap reject before the exact clip
                area = self._polygon_area_in_bbox(polygons, xmin, ymin, xmax, ymax)
                if area <= 0:
                    continue
                pct = round(100.0 * area / total_area, 1)
                if pct > 0.01:
                    out[name] = out.get(name, 0) + pct
            return out

        if self.provinces_loaded:
            province_items = [(n, info["polygons"], info.get("bbox")) for n, info in self.provinces.items()]
        else:
            province_items = [(info.get("province", n), info["polygons"], info.get("bbox"))
                               for n, info in self.districts.items()]
        district_items = [(n, info["polygons"], info.get("bbox")) for n, info in self.districts.items()]
        local_items = [(lb["name"], lb["polygons"], lb.get("bbox")) for lb in self.localbodies]
        pa_items = [(f'{pa["name"]} ({pa["category"]})', pa["polygons"], None) for pa in self.protected_areas]
        claimed_items = ([(self.claimed_area_name, self.claimed_area_polygons, None)]
                          if getattr(self, "claimed_area_polygons", None) else [])

        return {
            "province_pct": _pct_for(province_items),
            "district_pct": _pct_for(district_items),
            "local_pct": _pct_for(local_items),
            "protected_pct": _pct_for(pa_items),
            "claimed_pct": _pct_for(claimed_items),
        }
