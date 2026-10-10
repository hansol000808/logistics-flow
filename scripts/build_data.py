#!/usr/bin/env python3
"""Rebuild the research archive from explicitly supplied, local source files.

Python 3.11+, pandas and openpyxl are required. No original notebook code is
executed. Raw sources, notebook outputs and local paths are never exported.
This does not establish permission to publish a newly supplied source file.
"""
from __future__ import annotations

import argparse
import ast
import hashlib
import json
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
}

REVIEWED_SOURCE_HASHES = {
    "highway2021": "a2fffc2fdece0ca631a790ebe80a532d5c36730ec12242101e9c774b2cbcd118",
    "postal2020": "0e05429f65f471a1716fe27580c7a3ea6b36f853f4047f46b9d46e7355f5cb70",
}

SOURCES = [
    {"id": "highway2021", "title": "한국도로공사 2021년 수시교통량", "period": "2021", "unit": "대 (수시조사 시간=계, 기점·종점 합계)", "url": "https://data.ex.co.kr/portal/docu/docuList?datasetId=19", "policyUrl": "https://data.ex.co.kr/portal/guide/publicDataPolicy", "status": "reviewed_for_publication", "licenseNote": "공식 목록의 2021년 수시교통량.csv(fileId=705) 및 공공데이터 자유활용 정책 확인. 다운로드 서버 오류로 공식 파일과 바이트 대조는 미완료.", "reviewedAt": "2026-10-11", "rawPublished": False},
    {"id": "freightOD2020", "title": "2020년 지역 간 화물 OD 수송실적", "period": "2020", "unit": "톤/년", "url": "https://www.nlic.go.kr/", "status": "pending_publication_review", "licenseNote": "당시 원자료의 공개 이용조건 확인 전 수치 공개 보류.", "rawPublished": False},
    {"id": "postal2020", "title": "우체국물류지원단 총괄국별 배달물량 (20210831 과거 파일)", "period": "2020", "unit": "개", "url": "https://www.data.go.kr/data/15040740/fileData.do", "archiveUrl": "https://www.data.go.kr/tcs/dss/selectDpkDetailInfo.do?publicDataDetailPk=uddi%3A05cfada8-fc6b-49df-b2a6-9578ace72f90&publicDataHistSn=1", "status": "reviewed_for_publication", "licenseNote": "20210831 과거 자료 항목의 이용허락범위 제한 없음 확인. 공식 과거 CSV와 로컬 파일의 SHA256 일치.", "reviewedAt": "2026-10-11", "archiveSnapshot": "20210831", "rawPublished": False},
]


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
    require(len(road_lines) == 41, "Expected 41 hand-selected lines from the 2022 archive")
    return all_coordinates, road_lines


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
    return {"year": 2021, "unit": "대 (수시조사 시간=계, 기점·종점 합계)", "sourceId": "highway2021", "sourceRowCount": len(source), "totalDirectionRows": len(selected), "sectionCount": int(selected["구간"].nunique()), "features": features, "groupCounts": counts, "selectionNote": "2022년 노트북에서 수동 선택한 고정 구간 집합. 전체 531개 구간의 양방향 합계 순위로 자동 선정한 상위 N개가 아니다.", "aggregationNote": "시간=계인 기점·종점 두 행의 차종별 대수를 합산. 3~7종=당시 연구의 중소형화물, 8~12종=대형화물. 차종의 공식 분류 명칭을 재정의하지 않는다. 연간 총대수 또는 연평균 일교통량으로 해석하지 않는다.", "geometryNote": "2022년 노트북에 입력한 대략적 양 끝점 좌표를 직선으로 연결. 실제 도로 경로·지하터널 노선이 아니다."}


def build(args):
    source_dir = args.source_dir.resolve()
    paths = {key: source_dir / filename for key, filename in SOURCE_FILES.items()}
    if args.postal_file:
        paths["postal2020"] = args.postal_file.resolve()
    included_paths = {key: path for key, path in paths.items() if not (args.exclude_od and key == "freightOD2020")}
    for path in [*included_paths.values(), args.notebook]:
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
            if source["status"] == "reviewed_for_publication" and source["sha256"] != reviewed_hash:
                source["status"] = "pending_local_input_review"
        else:
            source["status"] = "withheld_pending_review"
        source["rawPublished"] = False
    data = {"schemaVersion": 1, "publicationReady": all(x["status"] == "reviewed_for_publication" for x in sources if x["derivedDataPublished"]), "project": {"title": "지하물류체계 구축을 위한 물동량 집중 구간 탐구", "year": 2022, "scope": "2022년 2학기 탐색적 시각화 연구 아카이브"}, "sources": sources, "regions": regions, "postal": {"year": 2020, "unit": "개", "sourceId": "postal2020", "includedTotal": sum(x["postal2020"] for x in regions), "nationalTotal": int(postal_row["총계"]), "excludedJeju": int(postal_row["제주지방우정청"]), "revisionNote": args.postal_note}, "od": None if args.exclude_od else freight_od(paths["freightOD2020"], args.expected_od), "roads": road_data(paths["highway2021"], selected_lines), "limitations": ["CJ택배 자료와 시각화, 창고 원자료, 개인정보, 타학생 자료는 공개 산출물에서 제외했다.", "2020년 화물 수송량·우체국 배달물량과 2021년 도로 교통량은 서로 다른 지표로 직접 합산할 수 없다.", "지역의 대표 좌표와 도로 양 끝점은 2022년 노트북에 입력한 근사 좌표다.", "도로 구간은 2022년 당시 수동 선택 결과이며 전국 최상위 구간 순위가 아니다.", "이 자료는 지하화 전환 수요, 공사비, 지질·지하공간, 경제성 또는 최적 노선을 검증하지 않는다."], "provenance": {"geometry": "2022년 기말과제 노트북의 좌표 및 선 선택을 AST로 추출. 원본 코드는 실행하지 않음.", "notebookSha256": sha256(args.notebook), "odValidationCells": 64 if args.expected_od and not args.exclude_od else None}}
    if args.exclude_od:
        data["limitations"].insert(0, "화물 OD 원자료의 공개 이용조건 확인 전까지 해당 수치는 공개본에서 제외했다.")
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"regions": len(regions), "odPairs": len(data["od"]["pairs"]) if data["od"] else 0, "roads": data["roads"]["groupCounts"], "publicationReady": data["publicationReady"]}, ensure_ascii=False))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-dir", type=Path, required=True, help="Local directory containing the three source datasets; not distributed")
    parser.add_argument("--notebook", type=Path, required=True, help="Original local 2022 notebook, used only for coordinates/selection")
    parser.add_argument("--output", type=Path, required=True, help="Destination research.json")
    parser.add_argument("--exclude-od", action="store_true", help="Withhold OD values pending source permission review; required for the initial public release")
    parser.add_argument("--expected-od", type=Path, help="Optional original df_final.xlsx for independent 64-cell reconciliation")
    parser.add_argument("--postal-file", type=Path, help="Explicit substitute postal CSV")
    parser.add_argument("--postal-encoding", default="cp949")
    parser.add_argument("--postal-note", default="2022년 연구 폴더에 보관된 2021-08-31 파일의 2020년 값(전국 181,675,471개). 2026년 공개본의 2020년 전국 합계는 176,748,550개로 다르며, 이 아카이브는 당시 파일값을 유지한다.")
    parser.add_argument("--source-metadata", type=Path, help="JSON array of reviewed source metadata; never grants publication permission by itself")
    build(parser.parse_args())


if __name__ == "__main__":
    main()
