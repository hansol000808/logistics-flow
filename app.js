/* Historical research explorer. The data file is the only content source. */
(() => {
  'use strict';

  const $ = (selector) => document.querySelector(selector);
  const $$ = (selector) => [...document.querySelectorAll(selector)];
  const number = (value) => Number(value).toLocaleString('ko-KR');
  const escape = (value) => String(value ?? '').replace(/[&<>"']/g, (char) => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[char]));
  const modeInfo = {
    smallMedium: {name:'중소형 화물차', color:'#bd5526', year:2021, unit:'대', value:'smallMedium'},
    large: {name:'대형 화물차', color:'#276d66', year:2021, unit:'대', value:'large'},
    postal: {name:'권역별 우체국 배달량', color:'#276d66', year:2020, unit:'개', value:'postal2020'},
  };
  const state = {data:null, mode:'smallMedium', selected:null, query:'', map:null, layer:null, drawn:[], regions:new Map(), view:'national'};

  function showMapStatus(message) {
    $('#map-status').textContent = message;
    $('#map-status').hidden = false;
  }

  function initMap() {
    if (!window.L) {
      showMapStatus('지도 구성 요소를 불러오지 못했습니다. 아래 목록에서 구간과 교통량을 확인할 수 있습니다.');
      $$('.map-view-controls button').forEach((button) => { button.disabled = true; });
      return;
    }
    state.map = L.map('map', {scrollWheelZoom:false, zoomControl:true, minZoom:5, maxZoom:16, preferCanvas:false, attributionControl:true});
    state.map.setView([36.25,127.75],7);
    const tiles = L.tileLayer('https://tile.openstreetmap.org/{z}/{x}/{y}.png', {
      maxZoom:19,
      attribution:'&copy; <a href="https://www.openstreetmap.org/copyright" target="_blank" rel="noopener noreferrer">OpenStreetMap</a> contributors',
    });
    let tileErrors = 0;
    let tilesLoaded = 0;
    tiles.on('tileerror', () => {
      tileErrors += 1;
      if (tileErrors >= 3) showMapStatus('배경지도를 불러오지 못한 부분이 있습니다. 구간 표시와 아래 목록은 계속 이용할 수 있습니다.');
    });
    tiles.on('tileload', () => {
      tilesLoaded += 1;
      if (tilesLoaded > tileErrors * 3) {
        $('#map-status').hidden = true;
        tileErrors = 0;
      }
    });
    tiles.addTo(state.map);
    state.layer = L.layerGroup().addTo(state.map);
    // No tile prefetching: only the current visible map is requested.
  }

  function itemsForMode() {
    if (state.mode === 'postal') {
      return (state.data.regions || []).filter((region) => Number.isFinite(region.postal2020)).sort((a,b) => b.postal2020 - a.postal2020);
    }
    return (state.data.roads?.features || []).filter((feature) => feature.groups?.includes(state.mode)).sort((a,b) => b[state.mode] - a[state.mode]);
  }

  function visibleItems() {
    const query = state.query.trim().toLocaleLowerCase('ko-KR').replace(/\s+/g,'');
    return itemsForMode().filter((item) => `${item.name}${item.from || ''}${item.to || ''}${item.route || ''}${(item.members || []).join('')}`.toLocaleLowerCase('ko-KR').replace(/\s+/g,'').includes(query));
  }

  function safeUrl(value) {
    try { const url = new URL(value); return ['https:','http:'].includes(url.protocol) ? url.href : null; } catch { return null; }
  }

  function renderSources() {
    const descriptions = {
      highway2021:'선정 구간별 중소형·대형 화물차 교통량을 기점·종점 양방향으로 합산했습니다. 수시조사의 합계이며, 연간 총량이나 일평균으로 해석하지 않습니다.',
      freightOD2020:'원자료의 공개 조건을 추가 확인해야 하므로 이 공개본에서는 수치를 제외했습니다. 당시 연구에서 사용한 자료의 출처만 기록합니다.',
      postal2020:'우체국 총괄국별 배달물량을 우정청 기준 8개 권역으로 묶었습니다. 제주를 제외했으며, 이 수치는 권역 간 이동량이 아닌 권역 내 배달실적입니다.',
    };
    $('#source-list').innerHTML = (state.data.sources || []).map((source,index) => {
      const url = safeUrl(source.url);
      const revision = source.id === 'postal2020' && state.data.postal?.revisionNote ? `<p>${escape(state.data.postal.revisionNote)}</p>` : '';
      const license = source.license || source.reuseNotice || source.licenseNote || '';
      return `<article class="source-row"><span class="source-number">${String(index+1).padStart(2,'0')}</span><div><h3>${escape(source.title)}${source.derivedDataPublished === false ? ' · 수치 공개 제외' : ''}</h3><p>${escape(descriptions[source.id] || source.description || '')}</p>${revision}${typeof license === 'string' && license ? `<p>${escape(license)}</p>` : ''}</div><div class="source-meta"><strong>${escape(source.period)}년 자료</strong><span>${escape(source.unit)}</span></div>${url ? `<a href="${escape(url)}" target="_blank" rel="noopener noreferrer">원출처 <span aria-hidden="true">↗</span><span class="sr-only">: ${escape(source.title)} (새 창)</span></a>` : ''}</article>`;
    }).join('');
  }

  function setView(view) {
    state.view = view;
    $$('.map-view-controls button').forEach((button) => {
      const active = button.dataset.view === view;
      button.classList.toggle('selected', active);
      button.setAttribute('aria-pressed', String(active));
    });
    if (!state.map) return;
    if (view === 'capital') state.map.fitBounds([[36.95,126.48],[37.87,127.65]], {padding:[22,35],animate:false});
    else state.map.fitBounds([[34.65,125.85],[38.35,129.75]], {padding:[20,20],animate:false});
  }

  function refreshMap() {
    if (!state.map) return;
    state.layer.clearLayers();
    state.drawn = [];
    const info = modeInfo[state.mode];
    const items = visibleItems();
    const max = Math.max(1, ...itemsForMode().map((item) => item[info.value] || 0));
    if (state.mode === 'postal') {
      // Area, rather than radius, is proportional to the delivery count.
      items.forEach((region) => {
        const selected = state.selected?.id === region.id;
        const circle = L.circleMarker(region.center,{radius:38*Math.sqrt(region.postal2020/max),color:selected ? '#a74822' : info.color,weight:selected ? 2.5 : 1.5,fillColor:selected ? '#bd5526' : info.color,fillOpacity:.28}).addTo(state.layer);
        circle.bindTooltip(`${escape(region.name)} · ${number(region.postal2020)}개`,{direction:'top'});
        circle.on('click',() => selectItem(region,false));
      });
      items.forEach((region) => {
        const icon = L.divIcon({className:'region-icon',html:`<span class="region-label">${escape(region.name)}</span>`,iconSize:[0,0],iconAnchor:[0,0]});
        const marker = L.marker(region.center,{icon,title:`${region.name} 권역 배달량 상세`,keyboard:true}).addTo(state.layer);
        marker.on('click',() => selectItem(region,false));
      });
      return;
    }
    [...items].reverse().forEach((item) => {
      if (!item.coordinates?.every((point) => Array.isArray(point) && point.length === 2 && point.every(Number.isFinite))) return;
      const width = 3.5;
      const selected = state.selected?.id === item.id;
      const line = L.polyline(item.coordinates, {color:selected ? '#9e3a15' : info.color,weight:selected ? width+3 : width,opacity:selected ? 1 : .85,lineCap:'round'}).addTo(state.layer);
      line.bindTooltip(`${escape(item.name)} · ${number(item[info.value])} ${info.unit}`, {sticky:true,direction:'top'});
      line.on('click', () => selectItem(item, false));
      state.drawn.push({line,item,width});
      item.coordinates.forEach((point) => {
        const circle = L.circleMarker(point, {radius:selected ? 3.5 : 2.5,color:info.color,weight:1,fillColor:'#fffef9',fillOpacity:1}).addTo(state.layer);
        circle.on('click', () => selectItem(item,false));
      });
    });
    const selected = state.drawn.find((entry) => entry.item.id === state.selected?.id);
    if (selected) selected.line.bringToFront();
  }

  function renderList() {
    const all = itemsForMode();
    const items = visibleItems();
    const info = modeInfo[state.mode];
    $('#list-count').textContent = `${items.length} / ${all.length}개`;
    $('#section-list').innerHTML = items.length ? items.map((item,index) => `<tr class="${state.selected?.id === item.id ? 'selected-row' : ''}"><td><button type="button" data-item-id="${escape(item.id)}" aria-pressed="${state.selected?.id === item.id}"><span class="row-number" aria-hidden="true">${String(index+1).padStart(2,'0')}</span>${escape(item.name)}<span class="row-arrow" aria-hidden="true">↗</span><span class="sr-only"> 상세 보기</span></button></td><td>${number(item[info.value])} <span>${escape(info.unit)}</span></td><td>${state.mode === 'postal' ? '2020 · 우체국 배달실적' : '2021 · 수시조사 합계'}</td></tr>`).join('') : '<tr><td colspan="3" class="table-empty">일치하는 구간이 없습니다. 다른 이름으로 검색해 보세요.</td></tr>';
  }

  function detailMarkup(item) {
    const info = modeInfo[state.mode];
    if (state.mode === 'postal') {
      const share = state.data.postal?.includedTotal ? `${(100*item.postal2020/state.data.postal.includedTotal).toFixed(1)}%` : '';
      return `<h3 id="detail-title">${escape(item.name)} 권역</h3><p class="detail-route">${escape((item.members || []).join(' · '))}<br>${escape(item.postalOffice || '')} 기준</p><div class="detail-value"><span class="small-label">2020년 우체국 배달물량</span><strong>${number(item.postal2020)}</strong><span class="value-unit">개</span></div>${share ? `<p class="detail-route">공개된 8개 권역 합계의 ${share}</p>` : ''}<p class="detail-note">2022년 보관본의 값 · 제주 제외<br>현재 공개본과 값이 다를 수 있습니다.<br>권역 간 이동량을 뜻하지 않습니다.</p>`;
    }
    return `<h3 id="detail-title">${escape(item.from)}<span class="detail-direction" aria-label="와">↔</span>${escape(item.to)}</h3><p class="detail-route">${escape(item.route || '')} · 2022년 연구 선정</p><div class="detail-value"><span class="small-label">${escape(info.name)} · 양방향 합계</span><strong>${number(item[info.value])}</strong><span class="value-unit">${escape(info.unit)}</span></div><p class="detail-note">2021년 수시교통량 · 시간 항목 ‘계’<br>일평균 또는 연간 총량을 뜻하지 않습니다.</p>`;
  }

  function selectItem(item, zoomTo) {
    state.selected = item;
    $('#detail-kicker').textContent = state.mode === 'postal' ? 'REGIONAL DELIVERIES' : 'SELECTED SECTION';
    $('#selection-detail').innerHTML = detailMarkup(item);
    // Update existing rows in place so keyboard focus stays on the chosen button.
    $$('#section-list button[data-item-id]').forEach((button) => {
      const selected = button.dataset.itemId === item.id;
      button.setAttribute('aria-pressed', String(selected));
      button.closest('tr').classList.toggle('selected-row',selected);
    });
    refreshMap();
    if (zoomTo && state.map && (item.center || item.coordinates?.every(Boolean))) {
      if (state.mode === 'postal') state.map.setView(item.center,8,{animate:false});
      else state.map.fitBounds(item.coordinates,{padding:[65,65],maxZoom:11,animate:false});
      $$('.map-view-controls button').forEach((button) => {button.classList.remove('selected');button.setAttribute('aria-pressed','false');});
    }
  }

  function setMode(mode) {
    state.mode = mode;
    state.query = '';
    $('#section-search').value = '';
    const postal = mode === 'postal';
    const info = modeInfo[mode];
    const items = itemsForMode();
    state.selected = items[0] || null;
    $$('.mode-button').forEach((button) => {
      const active = button.dataset.mode === mode;
      button.classList.toggle('active',active);
      button.setAttribute('aria-pressed',String(active));
    });
    $('#data-stamp').textContent = postal ? '2020년 우체국 배달량' : '2021년 도로 교통량';
    $('#legend-label').textContent = postal ? '원 면적 ∝ 배달량 · 대표 위치' : '2022년 연구 선정 구간';
    $('.legend-line').style.background = info.color;
    $('.legend-line').classList.toggle('legend-circle',postal);
    $('.map-note').textContent = postal ? '원은 우정청 기준 권역의 배달량을 나타내며 실제 서비스 영역과 다릅니다.' : '선은 두 지점의 연결을 나타내며 실제 도로 선형과 다릅니다.';
    $('#summary-label').textContent = postal ? '우정청 기준 연구 권역' : '연구 선정 구간';
    $('#summary-count').textContent = number(items.length);
    $('#summary-unit').textContent = postal ? '개 권역 · 제주 제외' : '개 구간';
    $('#mode-description').textContent = postal ? '2022년에 사용한 2020년 배달실적입니다. 원 면적이 배달량에 비례하며, 화물의 권역 간 이동을 나타내지 않습니다.' : '2022년 연구에서 수동으로 선택한 고정 구간입니다. 전국 자동 최적화나 전체 구간 순위가 아닙니다.';
    $('#list-title').textContent = postal ? '권역별 배달량 목록' : '선정 구간 목록';
    $('.data-table thead th:first-child').textContent = postal ? '권역' : '구간 / 연결';
    $('#table-value-heading').textContent = postal ? '배달량' : '양방향 교통량';
    $('#table-caption').textContent = postal ? '우정청 기준 8개 권역의 우체국 배달량. 권역 이름 버튼을 누르면 상세 정보를 확인할 수 있습니다.' : '지도에 표시된 선정 구간과 교통량. 구간 이름 버튼을 누르면 상세 정보를 확인할 수 있습니다.';
    $('#list-footnote').textContent = postal ? '2022년 보관본의 2020년 우체국 배달량입니다. 제주를 제외한 8개 권역이며, 현재 공개본과 차이가 있어 당시 값을 유지했습니다.' : '선정 구간 안에서 교통량이 많은 순서입니다. 2021년 수시조사 양방향 합계이며, 전국 전체 구간의 순위가 아닙니다.';
    renderList();
    if (state.selected) selectItem(state.selected,false);
    else {
      $('#selection-detail').innerHTML = '<h3 id="detail-title">공개 자료 준비 중</h3><p class="detail-note">이 관점의 데이터는 현재 공개본에 포함되지 않았습니다.</p>';
      refreshMap();
    }
    setView('national');
  }

  function bindEvents() {
    $$('.mode-button').forEach((button) => button.addEventListener('click', () => setMode(button.dataset.mode)));
    $('.mode-tabs').addEventListener('keydown', (event) => {
      if (!['ArrowRight','ArrowLeft','Home','End'].includes(event.key)) return;
      const buttons = $$('.mode-button').filter((button) => !button.disabled);
      const index = buttons.indexOf(document.activeElement);
      if (index < 0) return;
      event.preventDefault();
      const next = event.key === 'Home' ? 0 : event.key === 'End' ? buttons.length-1 : (index+(event.key === 'ArrowRight' ? 1 : -1)+buttons.length)%buttons.length;
      buttons[next].focus();
      setMode(buttons[next].dataset.mode);
    });
    $$('.map-view-controls button').forEach((button) => button.addEventListener('click', () => setView(button.dataset.view)));
    $('#section-search').addEventListener('input', (event) => {
      state.query = event.target.value;
      renderList();
      refreshMap();
    });
    $('#section-list').addEventListener('click', (event) => {
      const button = event.target.closest('button[data-item-id]');
      if (!button) return;
      const item = itemsForMode().find((entry) => entry.id === button.dataset.itemId);
      if (item) selectItem(item,true);
    });
  }

  async function start() {
    try {
      const response = await fetch('./data/research.json');
      if (!response.ok) throw new Error(`Research data: HTTP ${response.status}`);
      state.data = await response.json();
      (state.data.regions || []).forEach((region) => state.regions.set(region.id,region));
      if (!state.data.regions?.some((region) => Number.isFinite(region.postal2020))) {
        const postalButton = $('.mode-button[data-mode="postal"]');
        postalButton.disabled = true;
        postalButton.title = '권역별 배달량 자료는 현재 공개본에 포함되지 않았습니다.';
        postalButton.setAttribute('aria-label','권역별 배달량: 현재 공개본 미포함');
      }
      renderSources();
      initMap();
      bindEvents();
      setMode('smallMedium');
    } catch (error) {
      $('#selection-detail').innerHTML = '<h3 id="detail-title">자료를 불러오지 못했습니다.</h3><p class="detail-note">네트워크 연결을 확인한 뒤 페이지를 새로고침해 주세요.</p>';
      $('#section-list').innerHTML = '<tr><td colspan="3" class="table-empty">자료를 불러올 수 없습니다. 연구 방법과 출처는 GitHub 저장소에서도 확인할 수 있습니다.</td></tr>';
      $('#source-list').innerHTML = '<p class="notice">출처 정보는 <a href="https://github.com/hansol000808/logistics-flow">GitHub 저장소</a>에서 확인할 수 있습니다.</p>';
      $$('.mode-button, .map-view-controls button').forEach((button) => {button.disabled = true;});
      $('#section-search').disabled = true;
      showMapStatus('데이터를 불러오지 못했습니다. 잠시 후 새로고침해 주세요.');
      console.error(error);
    }
  }
  start();
})();
