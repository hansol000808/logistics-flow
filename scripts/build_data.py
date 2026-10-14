#!/usr/bin/env python3
"""Rebuild the research archive from explicitly supplied, local source files.

Python 3.11+, pandas and openpyxl are required. No original notebook code is
executed. Only the documented research fields are exported, never personal
contacts, notebook outputs, or local paths. Permission metadata records the
project owner's confirmation; it is not an official approval certificate.
"""
from __future__ import annotations

import argparse
import ast
import csv
import hashlib
import json
import re
from pathlib import Path

import pandas as pd


REGIONS = {
    "서울": {"members": ["서울"], "coordinateName": "서울", "postal": "서울지방우정청"},
    "경인": {"members": ["경기", "인천"], "coordinateName": "경인", "postal": "경인지방우정청"},
    "강원": {"members": ["강원"], "coordinateName": "강원", "postal": "강원지방우정청"},
    "충청": {"members": ["충북", "충남", "대전", "세종"], "coordinateName": "충청", "postal": "충청지방우정청"},
    "전북": {"members": ["전북"], "coordinateName": "전북", "postal": "전북지방우정청"},
    "광주전남": {"members": ["광주", "전남"], "coordinateName": "전남", "postal": "전남지방우정청"},
    "대구경북": {"members": ["대구", "경북"], "coordinateName": "경북", "postal": "경북지방우정청"},
    "부울경": {"members": ["부산", "울산", "경남"], "coordinateName": "부산", "postal": "부산지방우정청"},
}

SOURCE_FILES = {
    "highway2021": "2021년 수시교통량.csv",
    "freightOD2020": "OD별수송실적통계_2020_2020_221218.xlsx",
    "postal2020": "우체국물류지원단_총괄국별 배달물량_20210831.csv",
    "cjArchive": "CJ택배차량 운행량 월별 통계.csv",
}

REVIEWED_SOURCE_HASHES = {
    "highway2021": "a2fffc2fdece0ca631a790ebe80a532d5c36730ec12242101e9c774b2cbcd118",
    "postal2020": "0e05429f65f471a1716fe27580c7a3ea6b36f853f4047f46b9d46e7355f5cb70",
    "freightOD2020": "a0a80ec10862ae4cbb4ca58256e2b722b3f53d50cf6b33fb007231989f368223",
    "cjArchive": "a996a5465c1270403b6cadac5a1952f6775b8ad4a86bc3ba99ecbaeb019cba66",
    "seoulBoundary": "41f0926d164e2bf44bee10d21952a4d79d83796821100dcf28e12516d0c49943",
    "archiveGeometry": "fb7058b0fbabc70d5e634eab6ebfc8776ed21e1b70809d95fb1ff989b3719d90",
}

SOURCES = [
    {"id": "highway2021", "title": "한국도로공사 2021년 수시교통량", "period": "2021", "unit": "대 (수시조사 시간=계, 기점·종점 합계)", "url": "https://data.ex.co.kr/portal/docu/docuList?datasetId=19", "policyUrl": "https://data.ex.co.kr/portal/guide/publicDataPolicy", "status": "reviewed_for_publication", "licenseNote": "공식 목록의 2021년 수시교통량.csv(fileId=705) 및 공공데이터 자유활용 정책 확인. 다운로드 서버 오류로 공식 파일과 바이트 대조는 미완료.", "reviewedAt": "2026-10-11", "rawPublished": False},
    {"id": "freightOD2020", "title": "2020년 지역 간 화물 OD 수송실적", "period": "2020", "unit": "톤/년", "url": "https://www.nlic.go.kr/nlic/frghtRoad0010.action", "licenseNote": "프로젝트 작성자의 자료 사용 확인에 근거해 제공.", "rawPublished": False},
    {"id": "postal2020", "title": "우체국물류지원단 총괄국별 배달물량 (2021-08-31 제공 파일)", "period": "2020", "unit": "개", "url": "https://www.data.go.kr/data/15040740/fileData.do", "archiveUrl": "https://www.data.go.kr/tcs/dss/selectDpkDetailInfo.do?publicDataDetailPk=uddi%3A05cfada8-fc6b-49df-b2a6-9578ace72f90&publicDataHistSn=1", "status": "reviewed_for_publication", "licenseNote": "2021-08-31 제공 자료의 이용허락범위 제한 없음 확인. 공식 CSV와 분석 파일의 SHA256 일치.", "reviewedAt": "2026-10-11", "archiveSnapshot": "20210831", "rawPublished": False},
    {"id": "cjArchive", "title": "서울시 자치구단위 CJ택배차량 운행량 월별 통계 · 연구용 발췌", "period": "2020-03~2021-06 (구별 기준월 혼합)", "unit": "경유지 총건수(건)", "url": "https://bigdata.seoul.go.kr/", "licenseNote": "프로젝트 작성자의 자료 사용 확인에 근거해 제공.", "rawPublished": False},
    {"id": "seoulBoundary", "title": "서울 25개 자치구 경계 · 2013년 기준", "period": "2013", "unit": "GeoJSON 경계", "url": "https://github.com/southkorea/seoul-maps/blob/master/kostat/2013/json/seoul_municipalities_geo_simple.json", "licenseNote": "연구 노트북에 기록된 출처. 지도 HTML의 GeoJSON에서 2013년 기준 행정경계를 추출함. 공개는 프로젝트 소유자의 확인에 근거함.", "rawPublished": False},
    {"id": "archiveGeometry", "title": "연구 노트북의 좌표·선택 구간·시설 메모", "period": "2022", "unit": "근사 좌표", "url": "", "licenseNote": "프로젝트 소유자의 공개 지시에 따라 연구용 좌표·시설명만 추출. 현재 시설 위치·운영 상태를 보증하는 공공시설 DB가 아님.", "rawPublished": False},
]

for _source in SOURCES:
    if "status" in _source:
        _source["previousReviewStatus"] = _source["status"]
    _source.update(status="user_confirmed_for_publication", permissionBasis="project_owner_confirmation", confirmedAt="2026-10-14", officialApprovalVerified=False)


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def notebook_geometry(path: Path):
    """Read only literal coordinates and named PolyLine endpoints, never exec."""
    notebook = json.loads(path.read_text(encoding="utf-8"))
    all_coordinates = {}
    road_lines = []
    for cell in notebook["cells"]:
        source = "".join(cell.get("source", []))
        if cell.get("cell_type") != "code" or "folium.PolyLine" not in source:
            continue
        tree = ast.parse(source)
        coordinates = {}
        for node in ast.walk(tree):
            if isinstance(node, ast.Assign) and isinstance(node.targets[0], ast.Name):
                try:
                    value = ast.literal_eval(node.value)
                except (ValueError, TypeError, SyntaxError):
                    continue
                if isinstance(value, list) and len(value) == 2 and all(isinstance(x, (int, float)) for x in value):
                    coordinates[node.targets[0].id] = value
        all_coordinates.update(coordinates)
        if "df_map3" not in source:
            continue
        for node in ast.walk(tree):
            if not (isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) and node.func.attr == "PolyLine"):
                continue
            endpoints = node.args[0]
            require(isinstance(endpoints, ast.List) and len(endpoints.elts) == 2, "Unexpected road endpoints")
            require(all(isinstance(x, ast.Name) for x in endpoints.elts), "Road endpoints must be coordinate names")
            first, last = [x.id for x in endpoints.elts]
            color = next(ast.literal_eval(x.value) for x in node.keywords if x.arg == "color")
            require(color in ("red", "orange"), "Unexpected selection group")
            road_lines.append((first, last, color, [coordinates[first], coordinates[last]]))
    require(len(road_lines) == 41, "Expected 41 hand-selected research lines")
    return all_coordinates, road_lines


def notebook_facilities(path: Path):
    """Recover labeled research markers, including the commented green markers."""
    notebook = json.loads(path.read_text(encoding="utf-8"))
    facilities = []
    for cell in notebook["cells"]:
        source = "".join(cell.get("source", []))
        if cell.get("cell_type") != "code" or "df_map3" not in source:
            continue
        for line in source.splitlines():
            if "folium.Marker(" not in line:
                continue
            match = re.match(r"\s*#?\s*folium\.Marker\((\[[^\]]+\]),icon=folium\.Icon\(color='(blue|green)'\)\)\.add_to\(df_map3\)\s*##(.+?)\s*$", line)
            require(match is not None, "Unexpected facility marker syntax")
            coordinates = ast.literal_eval(match.group(1))
            require(len(coordinates) == 2 and all(isinstance(v, (int, float)) for v in coordinates), "Invalid facility coordinates")
            facilities.append({"id": f"facility-{len(facilities) + 1:02}", "name": match.group(3).strip(), "type": "port" if match.group(2) == "blue" else "logistics", "coordinates": coordinates, "note": "연구 노트북에 입력한 시설명과 근사 좌표. 현재 명칭·위치·운영 여부를 확인한 시설 목록이 아니다.", "sourceId": "archiveGeometry"})
    require(len(facilities) == 22 and sum(x["type"] == "logistics" for x in facilities) == 20, "Expected 20 logistics facilities and 2 ports")
    return facilities


def cj_data(path: Path, map_html: Path):
    source = pd.read_csv(path, encoding="cp949")
    name_column, period_column, value_column = "주소(구)(ADDR)", "운행년월(DRIVEN_YM)", "경유지_총건수(VIA_CNT)"
    require(len(source) == 25 and source[name_column].is_unique, "Expected one archived row per Seoul district")
    require(not source[[name_column, period_column, value_column]].isna().any().any(), "Missing CJ archive value")
    districts = []
    for _, row in source.sort_values(name_column).iterrows():
        month = str(int(row[period_column]))
        require(re.fullmatch(r"20\d{2}(0[1-9]|1[0-2])", month) is not None, "Invalid CJ month")
        require(int(row[value_column]) >= 0 and int(row[value_column]) == row[value_column], "Invalid CJ value")
        districts.append({"id": f"cj-{len(districts) + 1:02}", "name": str(row[name_column]), "period": f"{month[:4]}-{month[4:]}", "value": int(row[value_column])})
    # Read embedded JSON only. No original HTML or JavaScript is executed.
    html = map_html.read_text(encoding="utf-8")
    features_key = html.find('"features"')
    require(features_key >= 0, "Missing archived GeoJSON")
    start = html.rfind("{", 0, features_key)
    geometry, _ = json.JSONDecoder().raw_decode(html[start:])
    require(geometry.get("type") == "FeatureCollection" and len(geometry["features"]) == 25, "Expected 25 archived district boundaries")
    boundaries = {item["properties"]["name"]: item for item in geometry["features"]}
    require(set(boundaries) == {item["name"] for item in districts}, "CJ districts and archived geometry do not match")
    features = [{"type": "Feature", "id": item["id"], "properties": dict(item), "geometry": boundaries[item["name"]]["geometry"]} for item in districts]
    periods = sorted({item["period"] for item in districts})
    require(len(periods) == 15, "Expected the original archive's 15 mixed months")
    return {"sourceId": "cjArchive", "geometrySourceId": "seoulBoundary", "metric": value_column, "unit": "건", "yearNote": f"{periods[0]}~{periods[-1]}, 구별로 서로 다른 {len(periods)}개 기준월", "periods": periods, "districts": districts, "geojson": {"type": "FeatureCollection", "features": features}, "comparisonNote": "25개 구의 기준월이 서로 다르다. 같은 시점의 구별 물류 수요 비교나 우선순위로 해석할 수 없으며 경유지 총건수를 배송 완료 건수로 바꾸어 읽지 않는다.", "geometryNote": "지도에 사용한 서울 자치구 경계는 2013년 기준이다."}


def freight_od(path: Path, expected_path: Path | None):
    source = pd.read_excel(path, index_col=0)
    source.index = source.index.astype(str).str.strip()
    source.columns = source.columns.astype(str).str.strip()
    require(source.index.is_unique and source.columns.is_unique, "OD labels are not unique")
    order = list(REGIONS)
    matrix = [[int(source.loc[REGIONS[a]["members"], REGIONS[b]["members"]].to_numpy().sum()) for b in order] for a in order]
    require(all(value >= 0 for row in matrix for value in row), "Negative OD value")
    # The original df_final workbook is transposed. Compare names, not row numbers.
    if expected_path:
        stored = pd.read_excel(expected_path, index_col=0)
        original_columns = {"서울": "0", "강원": "8", "전북": "11", "경인": "경인", "충청": "충청", "광주전남": "광주전남", "대구경북": "대구경북", "부울경": "부울경"}
        stored.columns = stored.columns.astype(str)
        for i, origin in enumerate(order):
            for j, destination in enumerate(order):
                require(matrix[i][j] == int(stored.loc[destination, original_columns[origin]]), f"OD archive mismatch: {origin}/{destination}")
    pairs = [{"from": a, "to": b, "forward": matrix[i][j], "reverse": matrix[j][i], "total": matrix[i][j] + matrix[j][i]} for i, a in enumerate(order) for j, b in enumerate(order) if i < j]
    return {"year": 2020, "unit": "톤/년", "regionOrder": order, "matrix": matrix, "pairs": pairs, "total": sum(map(sum, matrix)), "interregionalTotal": sum(x["total"] for x in pairs), "sourceId": "freightOD2020", "matrixMeaning": "행=출발권역, 열=도착권역. 제주 제외. 대각선은 권역 내부 이동이며 지도 선에서 제외.", "pairMeaning": "서로 다른 두 권역의 양방향 수송량 합계"}


def road_data(path: Path, selected_lines):
    source = pd.read_csv(path, encoding="cp949")
    selected = source.loc[source["시간"].astype(str).str.strip() == "계"].copy()
    classes = [f"{x}종" for x in range(1, 13)]
    require(not selected[classes].isna().any().any(), "Missing vehicle class values")
    require((selected[classes].sum(axis=1) == selected["계"]).all(), "Vehicle class totals do not match")
    road_key = ["노선", "지점번호", "구간", "방향"]
    recorded_totals = selected.set_index(road_key)[classes].sort_index()
    hourly_totals = source.loc[source["시간"].astype(str).str.strip() != "계"].groupby(road_key)[classes].sum().sort_index()
    require(recorded_totals.equals(hourly_totals), "Hourly rows do not reconcile with recorded totals")
    selected["smallMedium"] = selected[[f"{x}종" for x in range(3, 8)]].sum(axis=1)
    selected["large"] = selected[[f"{x}종" for x in range(8, 13)]].sum(axis=1)
    selected["rankSmallMedium"] = selected["smallMedium"].rank(method="min", ascending=False).astype(int)
    selected["rankLarge"] = selected["large"].rank(method="min", ascending=False).astype(int)
    unique_features = {}
    for first, last, color, coordinates in selected_lines:
        matching = selected.loc[selected["구간"].isin([f"{first}~{last}", f"{last}~{first}"])]
        require(len(matching) == 2 and set(matching["방향"]) == {"기점", "종점"}, f"Expected both directions exactly once: {first}~{last}")
        require(matching["노선"].nunique() == 1, "Ambiguous road name")
        key = str(matching.iloc[0]["구간"])
        group = "smallMedium" if color == "red" else "large"
        if key in unique_features:
            unique_features[key]["groups"].append(group)
            continue
        unique_features[key] = {"id": f"road-{len(unique_features) + 1:02}", "name": key, "from": first, "to": last, "coordinates": coordinates, "groups": [group], "smallMedium": int(matching["smallMedium"].sum()), "large": int(matching["large"].sum()), "totalVehicles": int(matching["계"].sum()), "directionRows": 2, "route": str(matching.iloc[0]["노선"])}
    features = list(unique_features.values())
    counts = {"smallMedium": sum("smallMedium" in x["groups"] for x in features), "large": sum("large" in x["groups"] for x in features), "unique": len(features)}
    require(counts == {"smallMedium": 29, "large": 12, "unique": 40}, "Unexpected selection counts")
    require(len(source) == 26550 and len(selected) == 1062 and selected["구간"].nunique() == 531, "Source is not the expected 2021 archive")
    all_sections = []
    for (route, section), rows in selected.groupby(["노선", "구간"], sort=False):
        require(len(rows) == 2 and set(rows["방향"]) == {"기점", "종점"}, f"Unexpected directional rows: {route}/{section}")
        entry = {"id": f"section-{len(all_sections) + 1:03}", "name": str(section), "route": str(route), "smallMedium": int(rows["smallMedium"].sum()), "large": int(rows["large"].sum()), "totalVehicles": int(rows["계"].sum()), "directions": [{"direction": str(row["방향"]), "smallMedium": int(row["smallMedium"]), "large": int(row["large"]), "totalVehicles": int(row["계"]), "rankSmallMedium": int(row["rankSmallMedium"]), "rankLarge": int(row["rankLarge"])} for _, row in rows.iterrows()], "groups": []}
        if section in unique_features:
            original = unique_features[section]
            entry.update(groups=original["groups"], coordinates=original["coordinates"], selectedFeatureId=original["id"])
        all_sections.append(entry)
    require(len(all_sections) == 531, "Expected 531 complete sections")
    for entry in all_sections:
        for metric, rank_name in (("smallMedium", "rankSmallMedium"), ("large", "rankLarge")):
            entry[rank_name] = 1 + sum(other[metric] > entry[metric] for other in all_sections)
    return {"year": 2021, "unit": "대 (수시조사 시간=계, 기점·종점 합계)", "sourceId": "highway2021", "sourceRowCount": len(source), "totalDirectionRows": len(selected), "sectionCount": int(selected["구간"].nunique()), "features": features, "allSections": all_sections, "groupCounts": counts, "selectionNote": "분석 과정에서 수동 선택한 고정 구간 집합. 전체 531개 구간의 양방향 합계 순위로 자동 선정한 상위 N개가 아니다.", "rankingNote": "전체 구간 순위는 531개 구간의 양방향 합계 기준. 방향별 순위는 1,062개 방향행 기준. 큰 값부터 정렬하며 동률은 같은 순위, 다음 순위는 동률 개수만큼 건너뛴다.", "aggregationNote": "시간=계인 기점·종점 두 행의 차종별 대수를 합산. 3~7종=연구에서 분류한 중소형화물, 8~12종=대형화물. 차종의 공식 분류 명칭을 재정의하지 않는다. 연간 총대수 또는 연평균 일교통량으로 해석하지 않는다.", "geometryNote": "연구 노트북에 입력한 대략적 양 끝점 좌표를 직선으로 연결. 실제 도로 경로·지하터널 노선이 아니다. 좌표가 있는 연구 선정 40개 구간만 지도에 표시하며 전체 531개 구간은 표에서 조회한다."}


def export_csv(data, directory: Path):
    """Write six documented, field-limited public research tables (UTF-8 BOM)."""
    tables = []
    if data["od"]:
        tables.append(("od_2020_matrix.csv", "2020년 화물 OD 8권역 행렬", "톤/년", ["origin", *data["od"]["regionOrder"]], [[name, *row] for name, row in zip(data["od"]["regionOrder"], data["od"]["matrix"])]))
    else:
        # Remove only this builder's named output, so an omission cannot leave
        # an older downloadable OD table in the destination directory.
        (directory / "od_2020_matrix.csv").unlink(missing_ok=True)
    tables.append(("cj_districts.csv", "CJ 자치구별 경유지 총건수 · 혼합 기준월", "건", ["id", "district", "period", "via_count"], [[x["id"], x["name"], x["period"], x["value"]] for x in data["cj"]["districts"]]))
    sections = data["roads"]["allSections"]
    tables.append(("roads_2021_sections.csv", "2021년 도로 531구간 양방향 합계", "대", ["id", "section", "route", "small_medium_classes_3_7", "large_classes_8_12", "all_vehicle_classes", "rank_small_medium_531", "rank_large_531", "selection_groups"], [[x["id"], x["name"], x["route"], x["smallMedium"], x["large"], x["totalVehicles"], x["rankSmallMedium"], x["rankLarge"], "|".join(x["groups"])] for x in sections]))
    tables.append(("roads_2021_directions.csv", "2021년 도로 1,062방향 집계", "대", ["section_id", "section", "route", "direction", "small_medium_classes_3_7", "large_classes_8_12", "all_vehicle_classes", "rank_small_medium_1062", "rank_large_1062"], [[x["id"], x["name"], x["route"], row["direction"], row["smallMedium"], row["large"], row["totalVehicles"], row["rankSmallMedium"], row["rankLarge"]] for x in sections for row in x["directions"]]))
    tables.append(("facilities_2022.csv", "연구용 물류시설 20곳·항만 2곳", "근사 좌표", ["id", "name", "type", "latitude", "longitude", "note"], [[x["id"], x["name"], x["type"], *x["coordinates"], x["note"]] for x in data["facilities"]]))
    tables.append(("postal_2020_regions.csv", "2020년 우체국 8권역 배달물량", "개", ["region", "postal_office", "year", "volume", "source_snapshot"], [[x["name"], x["postalOffice"], 2020, x["postal2020"], "20210831"] for x in data["regions"]]))
    downloads = []
    for filename, title, unit, header, rows in tables:
        target = directory / filename
        with target.open("w", encoding="utf-8-sig", newline="") as stream:
            writer = csv.writer(stream, lineterminator="\n")
            writer.writerow(header)
            writer.writerows(rows)
        downloads.append({"id": filename.removesuffix(".csv"), "title": title, "href": f"data/{filename}", "format": "CSV (UTF-8 BOM)", "rows": len(rows), "unit": unit, "sha256": sha256(target)})
    return downloads


def build(args):
    source_dir = args.source_dir.resolve()
    paths = {key: source_dir / filename for key, filename in SOURCE_FILES.items()}
    map_html = args.map_html.resolve() if args.map_html else args.notebook.resolve().parent / "df_map1.html"
    paths.update(seoulBoundary=map_html, archiveGeometry=args.notebook.resolve())
    if args.postal_file:
        paths["postal2020"] = args.postal_file.resolve()
    included_paths = {key: path for key, path in paths.items() if not (args.exclude_od and key == "freightOD2020")}
    for path in included_paths.values():
        require(path.is_file(), f"Missing local input: {path.name}")
    coordinates, selected_lines = notebook_geometry(args.notebook)
    postal = pd.read_csv(paths["postal2020"], encoding=args.postal_encoding)
    postal_rows = postal.loc[postal["연도"].astype(str).str.strip() == "2020"]
    require(len(postal_rows) == 1, "Expected exactly one 2020 postal row")
    postal_row = postal_rows.iloc[0]
    postal_regions = [x for x in postal.columns if x.endswith("지방우정청")]
    require(int(postal_row[postal_regions].sum()) == int(postal_row["총계"]), "Postal national total mismatch")
    regions = [{"id": name, "name": name, "center": coordinates[info["coordinateName"]], "members": info["members"], "postal2020": int(postal_row[info["postal"]]), "postalSourceId": "postal2020", "postalOffice": info["postal"]} for name, info in REGIONS.items()]
    sources = json.loads(json.dumps(SOURCES))
    if args.source_metadata:
        updates = json.loads(args.source_metadata.read_text(encoding="utf-8"))
        require(isinstance(updates, list), "Source metadata must be a JSON array")
        for update in updates:
            matches = [x for x in sources if x["id"] == update.get("id")]
            require(len(matches) == 1, "Unknown source metadata id")
            matches[0].update(update)
    for source in sources:
        source["derivedDataPublished"] = source["id"] in included_paths
        if source["derivedDataPublished"]:
            source["sha256"] = sha256(paths[source["id"]])
            reviewed_hash = source.get("reviewedSha256", REVIEWED_SOURCE_HASHES.get(source["id"]))
            if source["status"] in {"reviewed_for_publication", "user_confirmed_for_publication"} and source["sha256"] != reviewed_hash:
                source["status"] = "pending_local_input_review"
        else:
            source["status"] = "omitted_by_build_option"
        source["rawPublished"] = False
    data = {
        "schemaVersion": 2,
        "publicationReady": all(x["status"] in {"reviewed_for_publication", "user_confirmed_for_publication"} for x in sources if x["derivedDataPublished"]),
        "publicationBasis": {"type": "project_owner_confirmation", "confirmedAt": "2026-10-14", "officialApprovalVerified": False, "note": "프로젝트 작성자의 자료 사용 확인에 근거해 제공."},
        "project": {"title": "지하물류체계 구축을 위한 물동량 집중 구간 탐구", "year": 2022, "scope": "물동량 집중 구간을 탐색하는 공간 분석 및 시각화"},
        "sources": sources,
        "regions": regions,
        "postal": {"year": 2020, "unit": "개", "sourceId": "postal2020", "includedTotal": sum(x["postal2020"] for x in regions), "nationalTotal": int(postal_row["총계"]), "excludedJeju": int(postal_row["제주지방우정청"]), "revisionNote": args.postal_note},
        "od": None if args.exclude_od else freight_od(paths["freightOD2020"], args.expected_od),
        "cj": cj_data(paths["cjArchive"], map_html),
        "roads": road_data(paths["highway2021"], selected_lines),
        "facilities": notebook_facilities(args.notebook),
        "limitations": [
            "CJ 자료는 구마다 기준월이 다른 25개 관측값이다. 동일 시점의 구별 수요 비교나 배송 완료 건수로 해석할 수 없다.",
            "2020년 화물 수송량·우체국 배달물량, 2021년 도로 교통량, CJ 경유지 총건수는 서로 다른 지표로 직접 합산할 수 없다.",
            "지역 대표점·도로 양 끝점·시설 위치는 연구 노트북에 입력한 근사 좌표다. 서울 자치구 경계는 2013년 기준이다.",
            "지도에 표시하는 도로 40구간은 분석 과정의 수동 선택 결과다. 전체 531개 구간 순위와 방향별 1,062행 순위는 표에서 별도로 조회한다.",
            "개인 대표자 성명·전화번호·학번·타학생 자료·수업자료는 공개 산출물에 포함하지 않는다.",
            "이 자료는 지하화 전환 수요, 공사비, 지질·지하공간, 경제성 또는 최적 노선을 검증하지 않는다.",
        ],
        "provenance": {"geometry": "연구 노트북의 좌표·선 선택·주석 시설명을 추출하고 지도 HTML의 GeoJSON을 읽음. 노트북 코드·HTML은 실행하지 않음.", "notebookSha256": sha256(args.notebook), "odValidationCells": 64 if args.expected_od and not args.exclude_od else None},
    }
    if args.exclude_od:
        data["limitations"].insert(0, "이 사용자 지정 빌드는 --exclude-od 옵션에 따라 화물 OD 수치를 생략했다.")
    args.output.parent.mkdir(parents=True, exist_ok=True)
    data["downloads"] = export_csv(data, args.output.parent)
    args.output.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"regions": len(regions), "odPairs": len(data["od"]["pairs"]) if data["od"] else 0, "roads": data["roads"]["groupCounts"], "allSections": len(data["roads"]["allSections"]), "cjDistricts": len(data["cj"]["districts"]), "facilities": len(data["facilities"]), "csvDownloads": len(data["downloads"]), "publicationReady": data["publicationReady"]}, ensure_ascii=False))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-dir", type=Path, required=True, help="Local directory containing the four source datasets; input files are not copied")
    parser.add_argument("--notebook", type=Path, required=True, help="Local research notebook, used only for coordinates/selection")
    parser.add_argument("--output", type=Path, required=True, help="Destination research.json")
    parser.add_argument("--map-html", type=Path, help="Original df_map1.html for its embedded Seoul boundaries; defaults beside the notebook")
    parser.add_argument("--exclude-od", action="store_true", help="Optionally omit OD values from a custom rebuild")
    parser.add_argument("--expected-od", type=Path, help="Optional original df_final.xlsx for independent 64-cell reconciliation")
    parser.add_argument("--postal-file", type=Path, help="Explicit substitute postal CSV")
    parser.add_argument("--postal-encoding", default="cp949")
    parser.add_argument("--postal-note", default="2021-08-31 제공 파일의 2020년 값(전국 181,675,471개)을 사용한다. 배포 파일 버전에 따라 같은 기준연도의 값이 달라질 수 있으므로, 이 분석은 해당 파일을 기준으로 한다.")
    parser.add_argument("--source-metadata", type=Path, help="JSON array of reviewed source metadata; never grants publication permission by itself")
    build(parser.parse_args())


if __name__ == "__main__":
    main()
