# 외부 소프트웨어와 지도 출처

## Leaflet

이 사이트는 [Leaflet 1.9.4](https://leafletjs.com/)를 사용합니다. 공식 npm 배포본의 실행 파일, 스타일, 이미지 및 라이선스를 `vendor/leaflet/`에 보관합니다.

- 배포본: https://registry.npmjs.org/leaflet/-/leaflet-1.9.4.tgz
- 배포본 SHA256: `84c65a256e50657896f54c33bd857b6849ebe94c817803be818bf32a3dde0b77`
- 라이선스: BSD 2-Clause, 원문은 [vendor/leaflet/LICENSE](vendor/leaflet/LICENSE)
- 저작권 표기는 원문에 따릅니다.

## OpenStreetMap

배경 지도는 OpenStreetMap의 표준 타일을 사용합니다. 지도 위에 `© OpenStreetMap contributors` 표시와 원문 링크를 유지합니다.

- [저작권과 라이선스](https://www.openstreetmap.org/copyright)
- [타일 이용정책](https://operations.osmfoundation.org/policies/tiles/)

타일은 방문자가 보고 있는 화면에 필요한 범위만 요청합니다. 타일 일괄 다운로드나 오프라인 배포 기능은 제공하지 않습니다. 브라우저의 기본 Referer와 HTTP 캐시 정책을 사용합니다. 외부 지도 서비스가 중단되어도 연구 데이터의 표와 설명은 사이트 자체에서 제공됩니다.

## 연구 자료

지도 라이브러리 라이선스와 연구 데이터의 사용조건은 별개입니다. 자료별 출처·기준시점·가공 방법은 [DATA_SOURCES.md](DATA_SOURCES.md)에 명시합니다. 제3자 데이터나 원문 도판 전체에 별도의 포괄적인 오픈소스 라이선스를 부여하지 않습니다.
