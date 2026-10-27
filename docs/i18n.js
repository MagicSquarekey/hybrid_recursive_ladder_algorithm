/* Hybrid Recursive Ladder — landing-page i18n.
 * Static, dependency-free. The English text in index.html is the fallback.
 * Supported: en, zh-CN, ja, ko, es, fr, de, pt-BR, ru, ar, hi.
 */
(() => {
  "use strict";

  const LINK_URLS = {
    disclosure:
      "https://github.com/MagicSquarekey/hybrid_recursive_ladder_algorithm/blob/main/docs/defensive-publication.md",
    prior:
      "https://github.com/MagicSquarekey/hybrid_recursive_ladder_algorithm/blob/main/docs/related-work.md",
    zenodo: "https://doi.org/10.5281/zenodo.23656844",
    citation:
      "https://github.com/MagicSquarekey/hybrid_recursive_ladder_algorithm/blob/main/CITATION.cff",
    readme:
      "https://github.com/MagicSquarekey/hybrid_recursive_ladder_algorithm#readme",
    spec:
      "https://github.com/MagicSquarekey/hybrid_recursive_ladder_algorithm/blob/main/docs/algorithm.md",
    zhArticle:
      "https://github.com/MagicSquarekey/hybrid_recursive_ladder_algorithm/blob/main/docs/articles/why-per-bucket-queries-are-slow.zh-CN.md",
  };

  const STATIC_LINK_TEXT = {
    zenodo: "10.5281/zenodo.23656844",
    citation: "CITATION.cff",
    zhArticle: "中文文章",
  };

  const LINK_TEXT = {
    en: { disclosure: "public disclosure", prior: "prior-art review", readme: "README", spec: "algorithm spec" },
    "zh-CN": { disclosure: "公开披露", prior: "先前工作综述", readme: "README", spec: "算法规范" },
    ja: { disclosure: "公開開示", prior: "関連研究レビュー", readme: "README", spec: "アルゴリズム仕様" },
    ko: { disclosure: "공개 공시", prior: "선행 연구 검토", readme: "README", spec: "알고리즘 명세" },
    es: { disclosure: "divulgación pública", prior: "revisión de trabajos previos", readme: "README", spec: "especificación del algoritmo" },
    fr: { disclosure: "divulgation publique", prior: "revue des travaux antérieurs", readme: "README", spec: "spécification de l'algorithme" },
    de: { disclosure: "Offenlegung", prior: "Review der Vorarbeiten", readme: "README", spec: "Algorithmus-Spezifikation" },
    "pt-BR": { disclosure: "divulgação pública", prior: "revisão de trabalhos anteriores", readme: "README", spec: "especificação do algoritmo" },
    ru: { disclosure: "публичное раскрытие", prior: "обзор предшествующих работ", readme: "README", spec: "спецификация алгоритма" },
    ar: { disclosure: "إفصاح عام", prior: "مراجعة الأعمال السابقة", readme: "README", spec: "مواصفات الخوارزمية" },
    hi: { disclosure: "सार्वजनिक प्रकटीकरण", prior: "पूर्व-कार्य समीक्षा", readme: "README", spec: "एल्गोरिदम विनिर्देश" },
  };

  const I18N = {
    en: {
      "nav.github": "GitHub",
      "nav.algorithm": "Algorithm",
      "nav.prior": "Prior art",
      "nav.article": "Article",
      "nav.cite": "Cite",
      "hero.eyebrow": "Query planning for bucket-limited time-series APIs",
      "hero.title": "Aggregate long ranges with a <span>handful of requests</span>, not thousands.",
      "hero.lead":
        "A per-bucket client pays one network round trip per output row. The Hybrid Recursive Ladder decomposes a range into complete calendar units, fetches each level once at the next finer aggregation, and folds locally—so the request count depends on the coarse units, not the minute buckets.",
      "hero.btn.github": "View on GitHub",
      "hero.btn.article": "Read the technical article",
      "hero.btn.disclosure": "Public disclosure",
      "problem.title": "The 139-second query",
      "problem.p1":
        "A production ThingsBoard query over a VPN took <strong>139 seconds</strong> for 1,140 statistical buckets. The arithmetic was trivial; the network was not. Each bucket needed up to four HTTP calls.",
      "problem.p2":
        "The obvious fixes—one coarse interval, pre-aggregation, pagination—all sacrifice something: output resolution, write access to the source, or the number of round trips.",
      "problem.quote":
        "The useful question: can the source return a coarser or finer aggregation over a contiguous run, so one request fills many output units?",
      "how.title": "How it works",
      "how.c1.title": "Decompose",
      "how.c1.body":
        "Split the range into complete calendar units. Emit only complete units; push partial left and right edges to the next finer level.",
      "how.c2.title": "Fetch once per level",
      "how.c2.body":
        "Fetch each maximal contiguous run sharing a fetch level at the next finer aggregation: months as days, days as hours, hours as minutes.",
      "how.c3.title": "Fold locally",
      "how.c3.body":
        "Sum the returned buckets into the output units. Optionally split against local coverage and fetch only the uncovered sub-ranges.",
      "bench.title": "Measured on a production deployment",
      "bench.scenario": "Scenario",
      "bench.segments": "Segments",
      "bench.requests": "Requests",
      "bench.time": "Time",
      "bench.r1": "2 days, minute level",
      "bench.r2": "1 year, day level",
      "bench.r3": "10 months, mixed levels",
      "bench.r4": "Local read, 42–90 segments",
      "bench.note":
        "Production numbers over a VPN; latency depends on network, source load and data density. The reproducible benchmark prints segment and request counts without a server.",
      "what.title": "What it is—and is not",
      "what.is.title": "It is a query-planning composition",
      "what.is.li1": "calendar hierarchy as the query plan, not just the display bucket;",
      "what.is.li2": "next-finer fetch plus local fold;",
      "what.is.li3": "fetch-level + contiguity grouping;",
      "what.is.li4": "coverage-aware gap filling;",
      "what.is.li5": "request count bounded by the source's per-request bucket limit.",
      "what.isnot.title": "It is not a new database or a new theory",
      "what.isnot.li1": "RRDtool / Whisper: multi-resolution archives;",
      "what.isnot.li2": "BTrDB: hierarchical time-partitioned summaries;",
      "what.isnot.li3": "TimescaleDB: hierarchical continuous aggregates;",
      "what.isnot.li4": "Druid: calendar period granularity;",
      "what.isnot.li5": "Prometheus / Grafana: point caps and single-step downsampling;",
      "what.isnot.li6": "segment trees and timing wheels: aligned decomposition and level cascade.",
      "what.note":
        "The method is published as a {disclosure} and released under the MIT License. The {prior} documents the closest systems and the differences.",
      "cite.title": "Cite this work",
      "cite.note":
        "Archived at Zenodo: {zenodo}. GitHub's \"Cite this repository\" button reads {citation}.",
      "try.title": "Try it",
      "try.note":
        "No database, no network, no configuration required for the demo. Documentation: {readme} · {spec} · {zhArticle}.",
      "meta.title": "Hybrid Recursive Ladder — query planning for bucket-limited time-series APIs",
      "meta.description":
        "Aggregate long time-series ranges with a handful of requests instead of thousands of per-bucket queries. A calendar-level query planner for APIs with a hard per-request bucket limit.",
    },

    "zh-CN": {
      "nav.github": "GitHub",
      "nav.algorithm": "算法",
      "nav.prior": "相关工作",
      "nav.article": "文章",
      "nav.cite": "引用",
      "hero.eyebrow": "面向「单请求桶数受限」时序 API 的查询规划",
      "hero.title": "用<span>少量请求</span>聚合长区间，而不是几千次。",
      "hero.lead":
        "逐桶客户端每输出一行就要一次网络往返。混合递归阶梯把区间分解为完整日历单位，每层用下一层聚合只取一次，再本地折叠——请求数取决于粗粒度单位，而不是分钟桶数。",
      "hero.btn.github": "在 GitHub 查看",
      "hero.btn.article": "阅读技术文章",
      "hero.btn.disclosure": "公开披露",
      "problem.title": "那个 139 秒的查询",
      "problem.p1":
        "一次经 VPN 的生产 ThingsBoard 查询为 1,140 个统计桶花了 <strong>139 秒</strong>。算术很轻松，网络不是。每个桶最多需要四次 HTTP 调用。",
      "problem.p2":
        "显而易见的修法——一个粗粒度区间、预聚合、分页——都要牺牲点什么：输出分辨率、对数据源的写权限，或者往返次数。",
      "problem.quote":
        "真正有用的问题是：数据源能否在一次请求里返回某个连续区间的更粗或更细聚合，从而让一次请求填满多个输出单位？",
      "how.title": "工作原理",
      "how.c1.title": "分解",
      "how.c1.body": "把区间切成完整日历单位。只输出完整单位；把左右残段交给下一层。",
      "how.c2.title": "每层取一次",
      "how.c2.body":
        "对共享同一取数层级的最大连续段，用下一层聚合一次取回：月按日、日按时、时按分。",
      "how.c3.title": "本地折叠",
      "how.c3.body":
        "把返回的桶累加成输出单位。可选地按本地覆盖切分，只补未覆盖的子区间。",
      "bench.title": "生产环境实测",
      "bench.scenario": "场景",
      "bench.segments": "段数",
      "bench.requests": "请求数",
      "bench.time": "时间",
      "bench.r1": "2 天，分钟级",
      "bench.r2": "1 年，日级",
      "bench.r3": "10 个月，混合层级",
      "bench.r4": "本地读，42–90 段",
      "bench.note":
        "生产数据经 VPN；延迟取决于网络、数据源负载和数据密度。可复现基准只打印段数和请求数，不需要服务器。",
      "what.title": "它是什么——以及不是什么",
      "what.is.title": "它是一种查询规划组合",
      "what.is.li1": "把日历层级当作查询计划，而不只是展示桶；",
      "what.is.li2": "下一层取数 + 本地折叠；",
      "what.is.li3": "取数层级 + 连续性分组；",
      "what.is.li4": "覆盖感知的空隙填充；",
      "what.is.li5": "请求数受数据源单请求桶数上限约束。",
      "what.isnot.title": "它不是新数据库，也不是新理论",
      "what.isnot.li1": "RRDtool / Whisper：多分辨率归档；",
      "what.isnot.li2": "BTrDB：按时间分区的层级摘要；",
      "what.isnot.li3": "TimescaleDB：层级连续聚合；",
      "what.isnot.li4": "Druid：日历周期粒度；",
      "what.isnot.li5": "Prometheus / Grafana：点数上限与单步降采样；",
      "what.isnot.li6": "线段树与时间轮：对齐分解与层级级联。",
      "what.note":
        "该方法以{disclosure}形式发布，并按 MIT 许可证开源。{prior}记录了最接近的系统及差异。",
      "cite.title": "引用本工作",
      "cite.note":
        "已归档至 Zenodo：{zenodo}。GitHub 的 “Cite this repository” 按钮读取 {citation}。",
      "try.title": "试一试",
      "try.note":
        "演示不需要数据库、网络或任何配置。文档：{readme} · {spec} · {zhArticle}。",
      "meta.title": "混合递归阶梯 — 面向桶数受限时序 API 的查询规划",
      "meta.description":
        "用少量请求聚合长时间序列区间，替代逐桶查询。面向单请求桶数硬上限 API 的日历级查询规划器。",
    },

    ja: {
      "nav.github": "GitHub",
      "nav.algorithm": "アルゴリズム",
      "nav.prior": "関連研究",
      "nav.article": "記事",
      "nav.cite": "引用",
      "hero.eyebrow": "バケット上限付き時系列 API のためのクエリプランニング",
      "hero.title": "長い区間を<span>わずかなリクエスト</span>で集計する。数千回ではなく。",
      "hero.lead":
        "バケット単位のクライアントは出力行ごとに 1 回のネットワーク往復を払います。Hybrid Recursive Ladder は区間を完全な暦単位に分解し、各層を次の細かい集約で 1 回だけ取得してローカルで畳み込みます。リクエスト数は分バケットではなく粗い単位で決まります。",
      "hero.btn.github": "GitHub で見る",
      "hero.btn.article": "技術記事を読む",
      "hero.btn.disclosure": "公開開示",
      "problem.title": "139 秒のクエリ",
      "problem.p1":
        "VPN 経由の本番 ThingsBoard クエリは 1,140 個の統計バケットに <strong>139 秒</strong> かかりました。計算は些細で、ネットワークが問題でした。各バケットに最大 4 回の HTTP 呼び出しが必要でした。",
      "problem.p2":
        "明白な修正——1 つの粗い interval、事前集約、ページング——は、出力解像度、データ源への書き込み権限、往復回数のいずれかを犠牲にします。",
      "problem.quote":
        "有用な問い：データ源は連続区間に対してより粗い／細かい集約を 1 回で返し、1 リクエストで多くの出力単位を埋められるか？",
      "how.title": "仕組み",
      "how.c1.title": "分解",
      "how.c1.body":
        "区間を完全な暦単位に分割します。完全な単位だけを出力し、左右の端数は次の細かい層へ送ります。",
      "how.c2.title": "層ごとに 1 回取得",
      "how.c2.body":
        "同じ取数層を共有する最大の連続区間を、次の細かい集約でまとめて取得します：月は日、日は時、時は分。",
      "how.c3.title": "ローカルで畳み込む",
      "how.c3.body":
        "返されたバケットを出力単位に合計します。必要ならローカルカバレッジで分割し、未カバーのサブ区間だけを取得します。",
      "bench.title": "本番環境での実測",
      "bench.scenario": "シナリオ",
      "bench.segments": "セグメント",
      "bench.requests": "リクエスト",
      "bench.time": "時間",
      "bench.r1": "2 日、分単位",
      "bench.r2": "1 年、日単位",
      "bench.r3": "10 か月、混合レベル",
      "bench.r4": "ローカル読み取り、42–90 セグメント",
      "bench.note":
        "本番値は VPN 経由。遅延はネットワーク、データ源負荷、データ密度に依存します。再現可能なベンチマークはサーバーなしでセグメント数とリクエスト数を出力します。",
      "what.title": "それが何であり、何でないか",
      "what.is.title": "クエリプランニングの組み合わせです",
      "what.is.li1": "カレンダー階層を表示バケットではなくクエリ計画として使う；",
      "what.is.li2": "次の細かい層の取得＋ローカル畳み込み；",
      "what.is.li3": "取数レベル＋連続性によるグループ化；",
      "what.is.li4": "カバレッジを考慮したギャップ埋め；",
      "what.is.li5": "リクエスト数はデータ源の 1 リクエストあたりバケット上限で決まる。",
      "what.isnot.title": "新しいデータベースでも新理論でもありません",
      "what.isnot.li1": "RRDtool / Whisper：マルチ解像度アーカイブ；",
      "what.isnot.li2": "BTrDB：時間分割の階層サマリー；",
      "what.isnot.li3": "TimescaleDB：階層的連続集約；",
      "what.isnot.li4": "Druid：暦期間の粒度；",
      "what.isnot.li5": "Prometheus / Grafana：点数上限と単一ステップのダウンサンプリング；",
      "what.isnot.li6": "セグメントツリーとタイミングホイール：整列分解とレベルカスケード。",
      "what.note":
        "本手法は{disclosure}として公開され、MIT ライセンスで提供されています。{prior}に最も近いシステムと違いが記載されています。",
      "cite.title": "引用",
      "cite.note":
        "Zenodo にアーカイブ済み：{zenodo}。GitHub の “Cite this repository” ボタンは {citation} を読みます。",
      "try.title": "試す",
      "try.note":
        "デモにデータベース、ネットワーク、設定は不要です。ドキュメント：{readme} · {spec} · {zhArticle}。",
      "meta.title": "Hybrid Recursive Ladder — バケット上限付き時系列 API のクエリプランニング",
      "meta.description":
        "数千回のバケット単位クエリの代わりに、わずかなリクエストで長い時系列区間を集計。1 リクエストあたりのバケット上限が厳しい API のための暦レベルクエリプランナー。",
    },

    ko: {
      "nav.github": "GitHub",
      "nav.algorithm": "알고리즘",
      "nav.prior": "선행 연구",
      "nav.article": "글",
      "nav.cite": "인용",
      "hero.eyebrow": "버킷 한도가 있는 시계열 API를 위한 쿼리 플래닝",
      "hero.title": "긴 구간을 <span>몇 번의 요청</span>으로 집계하세요. 수천 번이 아니라.",
      "hero.lead":
        "버킷 단위 클라이언트는 출력 행마다 네트워크 왕복 한 번을 지불합니다. Hybrid Recursive Ladder는 구간을 완전한 달력 단위로 분해하고, 각 계층을 다음 세밀한 집계로 한 번만 가져와 로컬에서 합산합니다. 따라서 요청 수는 분 버킷이 아니라 굵은 단위에 따라 결정됩니다.",
      "hero.btn.github": "GitHub에서 보기",
      "hero.btn.article": "기술 글 읽기",
      "hero.btn.disclosure": "공개 공시",
      "problem.title": "139초 쿼리",
      "problem.p1":
        "VPN을 통한 실제 ThingsBoard 쿼리는 1,140개 통계 버킷에 <strong>139초</strong>가 걸렸습니다. 계산은 사소했고 네트워크가 문제였습니다. 버킷마다 최대 네 번의 HTTP 호출이 필요했습니다.",
      "problem.p2":
        "뻔한 해법—하나의 굵은 interval, 사전 집계, 페이지네이션—은 출력 해상도, 데이터 소스 쓰기 권한, 왕복 횟수 중 하나를 희생합니다.",
      "problem.quote":
        "유용한 질문: 데이터 소스가 연속 구간에 대해 더 굵거나 더 세밀한 집계를 한 번에 반환해, 한 요청으로 여러 출력 단위를 채울 수 있는가?",
      "how.title": "동작 방식",
      "how.c1.title": "분해",
      "how.c1.body":
        "구간을 완전한 달력 단위로 나눕니다. 완전한 단위만 출력하고, 양쪽 끝의 부분 구간은 다음 세밀한 계층으로 넘깁니다.",
      "how.c2.title": "계층당 한 번 가져오기",
      "how.c2.body":
        "같은 가져오기 계층을 공유하는 최대 연속 구간을 다음 세밀한 집계로 한 번에 가져옵니다: 월은 일, 일은 시, 시는 분.",
      "how.c3.title": "로컬에서 합산",
      "how.c3.body":
        "반환된 버킷을 출력 단위로 합산합니다. 선택적으로 로컬 커버리지로 나누어 커버되지 않은 하위 구간만 가져옵니다.",
      "bench.title": "실제 배포 환경 측정",
      "bench.scenario": "시나리오",
      "bench.segments": "세그먼트",
      "bench.requests": "요청",
      "bench.time": "시간",
      "bench.r1": "2일, 분 단위",
      "bench.r2": "1년, 일 단위",
      "bench.r3": "10개월, 혼합 계층",
      "bench.r4": "로컬 읽기, 42–90 세그먼트",
      "bench.note":
        "실제 수치는 VPN 경유입니다. 지연은 네트워크, 소스 부하, 데이터 밀도에 따라 달라집니다. 재현 가능한 벤치마크는 서버 없이 세그먼트와 요청 수를 출력합니다.",
      "what.title": "무엇이고 무엇이 아닌가",
      "what.is.title": "쿼리 플래닝 조합입니다",
      "what.is.li1": "달력 계층을 표시 버킷이 아니라 쿼리 계획으로 사용;",
      "what.is.li2": "다음 세밀한 계층 가져오기 + 로컬 합산;",
      "what.is.li3": "가져오기 계층 + 연속성 그룹화;",
      "what.is.li4": "커버리지를 고려한 빈 구간 채우기;",
      "what.is.li5": "요청 수는 데이터 소스의 요청당 버킷 한도에 의해 제한됩니다.",
      "what.isnot.title": "새 데이터베이스도, 새 이론도 아닙니다",
      "what.isnot.li1": "RRDtool / Whisper: 다중 해상도 아카이브;",
      "what.isnot.li2": "BTrDB: 시간 분할 계층 요약;",
      "what.isnot.li3": "TimescaleDB: 계층적 연속 집계;",
      "what.isnot.li4": "Druid: 달력 기간 세분성;",
      "what.isnot.li5": "Prometheus / Grafana: 포인트 한도와 단일 단계 다운샘플링;",
      "what.isnot.li6": "세그먼트 트리와 타이밍 휠: 정렬 분해와 레벨 캐스케이드.",
      "what.note":
        "이 방법은 {disclosure}로 게시되었고 MIT 라이선스로 배포됩니다. {prior}에 가장 가까운 시스템과 차이가 정리되어 있습니다.",
      "cite.title": "인용",
      "cite.note":
        "Zenodo에 보관됨: {zenodo}. GitHub의 “Cite this repository” 버튼은 {citation}를 읽습니다.",
      "try.title": "사용해 보기",
      "try.note":
        "데모에는 데이터베이스, 네트워크, 설정이 필요 없습니다. 문서: {readme} · {spec} · {zhArticle}.",
      "meta.title": "Hybrid Recursive Ladder — 버킷 한도가 있는 시계열 API를 위한 쿼리 플래닝",
      "meta.description":
        "수천 번의 버킷별 쿼리 대신 몇 번의 요청으로 긴 시계열 구간을 집계합니다. 요청당 버킷 한도가 엄격한 API를 위한 달력 수준 쿼리 플래너.",
    },

    es: {
      "nav.github": "GitHub",
      "nav.algorithm": "Algoritmo",
      "nav.prior": "Trabajos previos",
      "nav.article": "Artículo",
      "nav.cite": "Citar",
      "hero.eyebrow": "Planificación de consultas para API de series temporales con límite de buckets",
      "hero.title": "Agrega rangos largos con un <span>puñado de peticiones</span>, no miles.",
      "hero.lead":
        "Un cliente por bucket paga un viaje de red por cada fila de salida. Hybrid Recursive Ladder descompone el rango en unidades de calendario completas, obtiene cada nivel una vez con la agregación del nivel más fino y suma localmente; así el número de peticiones depende de las unidades gruesas, no de los buckets de minuto.",
      "hero.btn.github": "Ver en GitHub",
      "hero.btn.article": "Leer el artículo técnico",
      "hero.btn.disclosure": "Divulgación pública",
      "problem.title": "La consulta de 139 segundos",
      "problem.p1":
        "Una consulta real de ThingsBoard por VPN tardó <strong>139 segundos</strong> para 1.140 buckets estadísticos. La aritmética era trivial; la red no. Cada bucket necesitaba hasta cuatro llamadas HTTP.",
      "problem.p2":
        "Las soluciones obvias —un intervalo grueso, preagregación, paginación— sacrifican algo: resolución de salida, acceso de escritura a la fuente o número de viajes.",
      "problem.quote":
        "La pregunta útil: ¿puede la fuente devolver una agregación más gruesa o más fina sobre un tramo contiguo, para que una petición llene muchas unidades de salida?",
      "how.title": "Cómo funciona",
      "how.c1.title": "Descomponer",
      "how.c1.body":
        "Divide el rango en unidades de calendario completas. Emite solo unidades completas; envía los bordes parciales izquierdo y derecho al siguiente nivel más fino.",
      "how.c2.title": "Obtener una vez por nivel",
      "how.c2.body":
        "Obtén cada tramo contiguo máximo que comparte nivel de obtención con la agregación del siguiente nivel más fino: meses como días, días como horas, horas como minutos.",
      "how.c3.title": "Sumar localmente",
      "how.c3.body":
        "Suma los buckets devueltos en las unidades de salida. Opcionalmente divide contra la cobertura local y obtén solo los subrangos no cubiertos.",
      "bench.title": "Medido en un despliegue real",
      "bench.scenario": "Escenario",
      "bench.segments": "Segmentos",
      "bench.requests": "Peticiones",
      "bench.time": "Tiempo",
      "bench.r1": "2 días, nivel minuto",
      "bench.r2": "1 año, nivel día",
      "bench.r3": "10 meses, niveles mixtos",
      "bench.r4": "Lectura local, 42–90 segmentos",
      "bench.note":
        "Números de producción por VPN; la latencia depende de la red, la carga de la fuente y la densidad de datos. El benchmark reproducible imprime segmentos y peticiones sin servidor.",
      "what.title": "Qué es—y qué no es",
      "what.is.title": "Es una composición de planificación de consultas",
      "what.is.li1": "jerarquía de calendario como plan de consulta, no solo como bucket de visualización;",
      "what.is.li2": "obtención del siguiente nivel más fino más suma local;",
      "what.is.li3": "agrupación por nivel de obtención y contigüidad;",
      "what.is.li4": "relleno de huecos consciente de la cobertura;",
      "what.is.li5": "número de peticiones acotado por el límite de buckets por petición de la fuente.",
      "what.isnot.title": "No es una nueva base de datos ni una nueva teoría",
      "what.isnot.li1": "RRDtool / Whisper: archivos multirresolución;",
      "what.isnot.li2": "BTrDB: resúmenes jerárquicos particionados por tiempo;",
      "what.isnot.li3": "TimescaleDB: agregados continuos jerárquicos;",
      "what.isnot.li4": "Druid: granularidad de periodos de calendario;",
      "what.isnot.li5": "Prometheus / Grafana: límites de puntos y downsampling de un paso;",
      "what.isnot.li6": "árboles de segmentos y timing wheels: descomposición alineada y cascada de niveles.",
      "what.note":
        "El método se publica como {disclosure} y se distribuye bajo licencia MIT. La {prior} documenta los sistemas más cercanos y las diferencias.",
      "cite.title": "Citar este trabajo",
      "cite.note":
        "Archivado en Zenodo: {zenodo}. El botón “Cite this repository” de GitHub lee {citation}.",
      "try.title": "Pruébalo",
      "try.note":
        "La demo no necesita base de datos, red ni configuración. Documentación: {readme} · {spec} · {zhArticle}.",
      "meta.title": "Hybrid Recursive Ladder — planificación de consultas para API de series temporales con límite de buckets",
      "meta.description":
        "Agrega rangos largos de series temporales con un puñado de peticiones en lugar de miles de consultas por bucket. Un planificador de consultas de nivel calendario para API con límite estricto de buckets por petición.",
    },

    fr: {
      "nav.github": "GitHub",
      "nav.algorithm": "Algorithme",
      "nav.prior": "Travaux antérieurs",
      "nav.article": "Article",
      "nav.cite": "Citer",
      "hero.eyebrow": "Planification de requêtes pour API de séries temporelles à limite de compartiments",
      "hero.title": "Agrégez de longues plages avec une <span>poignée de requêtes</span>, pas des milliers.",
      "hero.lead":
        "Un client par compartiment paie un aller-retour réseau par ligne de sortie. Hybrid Recursive Ladder décompose la plage en unités calendaires complètes, récupère chaque niveau une fois avec l'agrégation du niveau plus fin et additionne localement ; le nombre de requêtes dépend donc des unités grossières, pas des compartiments minute.",
      "hero.btn.github": "Voir sur GitHub",
      "hero.btn.article": "Lire l'article technique",
      "hero.btn.disclosure": "Divulgation publique",
      "problem.title": "La requête de 139 secondes",
      "problem.p1":
        "Une requête ThingsBoard en production via VPN a pris <strong>139 secondes</strong> pour 1 140 compartiments statistiques. L'arithmétique était triviale ; le réseau ne l'était pas. Chaque compartiment nécessitait jusqu'à quatre appels HTTP.",
      "problem.p2":
        "Les correctifs évidents —un intervalle grossier, la pré-agrégation, la pagination— sacrifient quelque chose : la résolution de sortie, l'accès en écriture à la source ou le nombre d'allers-retours.",
      "problem.quote":
        "La bonne question : la source peut-elle renvoyer une agrégation plus grossière ou plus fine sur un tronçon contigu, afin qu'une requête remplisse plusieurs unités de sortie ?",
      "how.title": "Comment ça marche",
      "how.c1.title": "Décomposer",
      "how.c1.body":
        "Découpez la plage en unités calendaires complètes. N'émettez que les unités complètes ; poussez les bords partiels gauche et droit au niveau plus fin.",
      "how.c2.title": "Récupérer une fois par niveau",
      "how.c2.body":
        "Récupérez chaque tronçon contigu maximal partageant un niveau avec l'agrégation du niveau plus fin : les mois en jours, les jours en heures, les heures en minutes.",
      "how.c3.title": "Additionner localement",
      "how.c3.body":
        "Additionnez les compartiments renvoyés dans les unités de sortie. Divisez éventuellement selon la couverture locale et ne récupérez que les sous-plages non couvertes.",
      "bench.title": "Mesuré sur un déploiement de production",
      "bench.scenario": "Scénario",
      "bench.segments": "Segments",
      "bench.requests": "Requêtes",
      "bench.time": "Temps",
      "bench.r1": "2 jours, niveau minute",
      "bench.r2": "1 an, niveau jour",
      "bench.r3": "10 mois, niveaux mixtes",
      "bench.r4": "Lecture locale, 42–90 segments",
      "bench.note":
        "Chiffres de production via VPN ; la latence dépend du réseau, de la charge de la source et de la densité des données. Le benchmark reproductible imprime les segments et les requêtes sans serveur.",
      "what.title": "Ce que c'est—et ce que ce n'est pas",
      "what.is.title": "C'est une composition de planification de requêtes",
      "what.is.li1": "la hiérarchie calendaire comme plan de requête, pas seulement comme compartiment d'affichage ;",
      "what.is.li2": "récupération du niveau plus fin plus addition locale ;",
      "what.is.li3": "regroupement par niveau de récupération et contiguïté ;",
      "what.is.li4": "remplissage des trous conscient de la couverture ;",
      "what.is.li5": "nombre de requêtes borné par la limite de compartiments par requête de la source.",
      "what.isnot.title": "Ce n'est pas une nouvelle base de données ni une nouvelle théorie",
      "what.isnot.li1": "RRDtool / Whisper : archives multi-résolution ;",
      "what.isnot.li2": "BTrDB : résumés hiérarchiques partitionnés par temps ;",
      "what.isnot.li3": "TimescaleDB : agrégats continus hiérarchiques ;",
      "what.isnot.li4": "Druid : granularité des périodes calendaires ;",
      "what.isnot.li5": "Prometheus / Grafana : plafonds de points et downsampling en une étape ;",
      "what.isnot.li6": "arbres de segments et timing wheels : décomposition alignée et cascade de niveaux.",
      "what.note":
        "La méthode est publiée comme {disclosure} et distribuée sous licence MIT. La {prior} documente les systèmes les plus proches et les différences.",
      "cite.title": "Citer ce travail",
      "cite.note":
        "Archivé sur Zenodo : {zenodo}. Le bouton « Cite this repository » de GitHub lit {citation}.",
      "try.title": "Essayer",
      "try.note":
        "La démo ne nécessite ni base de données, ni réseau, ni configuration. Documentation : {readme} · {spec} · {zhArticle}.",
      "meta.title": "Hybrid Recursive Ladder — planification de requêtes pour API de séries temporelles à limite de compartiments",
      "meta.description":
        "Agrégez de longues plages de séries temporelles avec une poignée de requêtes au lieu de milliers de requêtes par compartiment. Un planificateur de requêtes calendaire pour API à limite stricte de compartiments par requête.",
    },

    de: {
      "nav.github": "GitHub",
      "nav.algorithm": "Algorithmus",
      "nav.prior": "Vorarbeiten",
      "nav.article": "Artikel",
      "nav.cite": "Zitieren",
      "hero.eyebrow": "Query-Planung für Zeitreihen-APIs mit Bucket-Limit",
      "hero.title": "Lange Bereiche mit einer <span>Handvoll Anfragen</span> aggregieren, nicht mit Tausenden.",
      "hero.lead":
        "Ein Bucket-Client zahlt pro Ausgabezeile einen Netzwerk-Roundtrip. Der Hybrid Recursive Ladder zerlegt den Bereich in vollständige Kalendereinheiten, ruft jede Ebene einmal mit der nächstfeineren Aggregation ab und summiert lokal — die Anzahl der Anfragen hängt von den groben Einheiten ab, nicht von den Minuten-Buckets.",
      "hero.btn.github": "Auf GitHub ansehen",
      "hero.btn.article": "Technischen Artikel lesen",
      "hero.btn.disclosure": "Offenlegung",
      "problem.title": "Die 139-Sekunden-Abfrage",
      "problem.p1":
        "Eine produktive ThingsBoard-Abfrage über VPN dauerte <strong>139 Sekunden</strong> für 1.140 statistische Buckets. Die Arithmetik war trivial; das Netzwerk nicht. Jeder Bucket brauchte bis zu vier HTTP-Aufrufe.",
      "problem.p2":
        "Die naheliegenden Lösungen —ein grobes Intervall, Voraggregation, Pagination— opfern etwas: Ausgabeauflösung, Schreibzugriff auf die Quelle oder die Anzahl der Roundtrips.",
      "problem.quote":
        "Die nützliche Frage: Kann die Quelle eine gröbere oder feinere Aggregation über einen zusammenhängenden Lauf liefern, sodass eine Anfrage viele Ausgabeeinheiten füllt?",
      "how.title": "So funktioniert es",
      "how.c1.title": "Zerlegen",
      "how.c1.body":
        "Zerlege den Bereich in vollständige Kalendereinheiten. Gib nur vollständige Einheiten aus; schiebe partielle linke und rechte Ränder auf die nächstfeinere Ebene.",
      "how.c2.title": "Einmal pro Ebene abrufen",
      "how.c2.body":
        "Rufe jeden maximalen zusammenhängenden Lauf mit gleicher Abrufebene mit der nächstfeineren Aggregation ab: Monate als Tage, Tage als Stunden, Stunden als Minuten.",
      "how.c3.title": "Lokal falten",
      "how.c3.body":
        "Summiere die zurückgegebenen Buckets in die Ausgabeeinheiten. Optional gegen lokale Abdeckung aufteilen und nur die nicht abgedeckten Teilbereiche abrufen.",
      "bench.title": "Auf einem Produktionssystem gemessen",
      "bench.scenario": "Szenario",
      "bench.segments": "Segmente",
      "bench.requests": "Anfragen",
      "bench.time": "Zeit",
      "bench.r1": "2 Tage, Minutenebene",
      "bench.r2": "1 Jahr, Tagesebene",
      "bench.r3": "10 Monate, gemischte Ebenen",
      "bench.r4": "Lokales Lesen, 42–90 Segmente",
      "bench.note":
        "Produktionswerte über VPN; die Latenz hängt von Netzwerk, Quellenlast und Datendichte ab. Der reproduzierbare Benchmark gibt Segmente und Anfragen ohne Server aus.",
      "what.title": "Was es ist—und was nicht",
      "what.is.title": "Es ist eine Query-Planungs-Komposition",
      "what.is.li1": "Kalenderhierarchie als Abfrageplan, nicht nur als Anzeige-Bucket;",
      "what.is.li2": "Abruf der nächstfeineren Ebene plus lokale Faltung;",
      "what.is.li3": "Gruppierung nach Abrufebene und Zusammenhängigkeit;",
      "what.is.li4": "abdeckungsbewusstes Füllen von Lücken;",
      "what.is.li5": "Anfragenzahl begrenzt durch das Bucket-Limit pro Anfrage der Quelle.",
      "what.isnot.title": "Es ist keine neue Datenbank und keine neue Theorie",
      "what.isnot.li1": "RRDtool / Whisper: Multi-Resolution-Archive;",
      "what.isnot.li2": "BTrDB: hierarchische, zeitpartitionierte Zusammenfassungen;",
      "what.isnot.li3": "TimescaleDB: hierarchische kontinuierliche Aggregate;",
      "what.isnot.li4": "Druid: Granularität von Kalenderperioden;",
      "what.isnot.li5": "Prometheus / Grafana: Punktelimits und einstufiges Downsampling;",
      "what.isnot.li6": "Segmentbäume und Timing Wheels: ausgerichtete Zerlegung und Ebenenkaskade.",
      "what.note":
        "Die Methode ist als {disclosure} veröffentlicht und unter der MIT-Lizenz freigegeben. Die {prior} dokumentiert die nächsten Systeme und die Unterschiede.",
      "cite.title": "Diese Arbeit zitieren",
      "cite.note":
        "Bei Zenodo archiviert: {zenodo}. Der GitHub-Button „Cite this repository“ liest {citation}.",
      "try.title": "Ausprobieren",
      "try.note":
        "Die Demo braucht keine Datenbank, kein Netzwerk und keine Konfiguration. Dokumentation: {readme} · {spec} · {zhArticle}.",
      "meta.title": "Hybrid Recursive Ladder — Query-Planung für Zeitreihen-APIs mit Bucket-Limit",
      "meta.description":
        "Lange Zeitreihenbereiche mit einer Handvoll Anfragen statt Tausenden Bucket-Abfragen aggregieren. Ein kalendergestützter Query-Planer für APIs mit hartem Bucket-Limit pro Anfrage.",
    },

    "pt-BR": {
      "nav.github": "GitHub",
      "nav.algorithm": "Algoritmo",
      "nav.prior": "Trabalhos anteriores",
      "nav.article": "Artigo",
      "nav.cite": "Citar",
      "hero.eyebrow": "Planejamento de consultas para APIs de séries temporais com limite de buckets",
      "hero.title": "Agregue intervalos longos com um <span>punhado de requisições</span>, não milhares.",
      "hero.lead":
        "Um cliente por bucket paga uma ida e volta de rede por linha de saída. O Hybrid Recursive Ladder decompõe o intervalo em unidades de calendário completas, busca cada nível uma vez com a agregação do nível mais fino e soma localmente — o número de requisições depende das unidades grossas, não dos buckets de minuto.",
      "hero.btn.github": "Ver no GitHub",
      "hero.btn.article": "Ler o artigo técnico",
      "hero.btn.disclosure": "Divulgação pública",
      "problem.title": "A consulta de 139 segundos",
      "problem.p1":
        "Uma consulta real do ThingsBoard via VPN levou <strong>139 segundos</strong> para 1.140 buckets estatísticos. A aritmética era trivial; a rede não. Cada bucket precisava de até quatro chamadas HTTP.",
      "problem.p2":
        "As correções óbvias —um intervalo grosso, pré-agregação, paginação— sacrificam algo: resolução de saída, acesso de escrita à fonte ou número de idas e voltas.",
      "problem.quote":
        "A pergunta útil: a fonte pode retornar uma agregação mais grossa ou mais fina sobre um trecho contíguo, para que uma requisição preencha muitas unidades de saída?",
      "how.title": "Como funciona",
      "how.c1.title": "Decompor",
      "how.c1.body":
        "Divida o intervalo em unidades de calendário completas. Emita apenas unidades completas; empurre as bordas parciais esquerda e direita para o próximo nível mais fino.",
      "how.c2.title": "Buscar uma vez por nível",
      "how.c2.body":
        "Busque cada trecho contíguo máximo que compartilha um nível de busca com a agregação do próximo nível mais fino: meses como dias, dias como horas, horas como minutos.",
      "how.c3.title": "Somar localmente",
      "how.c3.body":
        "Some os buckets retornados nas unidades de saída. Opcionalmente divida pela cobertura local e busque apenas os subintervalos não cobertos.",
      "bench.title": "Medido em um ambiente de produção",
      "bench.scenario": "Cenário",
      "bench.segments": "Segmentos",
      "bench.requests": "Requisições",
      "bench.time": "Tempo",
      "bench.r1": "2 dias, nível minuto",
      "bench.r2": "1 ano, nível dia",
      "bench.r3": "10 meses, níveis mistos",
      "bench.r4": "Leitura local, 42–90 segmentos",
      "bench.note":
        "Números de produção via VPN; a latência depende da rede, da carga da fonte e da densidade dos dados. O benchmark reproduzível imprime segmentos e requisições sem servidor.",
      "what.title": "O que é—e o que não é",
      "what.is.title": "É uma composição de planejamento de consultas",
      "what.is.li1": "hierarquia de calendário como plano de consulta, não apenas como bucket de exibição;",
      "what.is.li2": "busca do próximo nível mais fino mais soma local;",
      "what.is.li3": "agrupamento por nível de busca e contiguidade;",
      "what.is.li4": "preenchimento de lacunas ciente da cobertura;",
      "what.is.li5": "número de requisições limitado pelo limite de buckets por requisição da fonte.",
      "what.isnot.title": "Não é um novo banco de dados nem uma nova teoria",
      "what.isnot.li1": "RRDtool / Whisper: arquivos multirresolução;",
      "what.isnot.li2": "BTrDB: resumos hierárquicos particionados por tempo;",
      "what.isnot.li3": "TimescaleDB: agregados contínuos hierárquicos;",
      "what.isnot.li4": "Druid: granularidade de períodos de calendário;",
      "what.isnot.li5": "Prometheus / Grafana: limites de pontos e downsampling de um passo;",
      "what.isnot.li6": "árvores de segmentos e timing wheels: decomposição alinhada e cascata de níveis.",
      "what.note":
        "O método é publicado como {disclosure} e distribuído sob a licença MIT. A {prior} documenta os sistemas mais próximos e as diferenças.",
      "cite.title": "Citar este trabalho",
      "cite.note":
        "Arquivado no Zenodo: {zenodo}. O botão “Cite this repository” do GitHub lê {citation}.",
      "try.title": "Experimente",
      "try.note":
        "A demo não precisa de banco de dados, rede ou configuração. Documentação: {readme} · {spec} · {zhArticle}.",
      "meta.title": "Hybrid Recursive Ladder — planejamento de consultas para APIs de séries temporais com limite de buckets",
      "meta.description":
        "Agregue intervalos longos de séries temporais com um punhado de requisições em vez de milhares de consultas por bucket. Um planejador de consultas em nível de calendário para APIs com limite rígido de buckets por requisição.",
    },

    ru: {
      "nav.github": "GitHub",
      "nav.algorithm": "Алгоритм",
      "nav.prior": "Предшествующие работы",
      "nav.article": "Статья",
      "nav.cite": "Цитирование",
      "hero.eyebrow": "Планирование запросов для API временных рядов с лимитом бакетов",
      "hero.title": "Агрегируйте длинные диапазоны <span>несколькими запросами</span>, а не тысячами.",
      "hero.lead":
        "Клиент с запросом на каждый бакет платит один сетевой обмен на каждую выходную строку. Hybrid Recursive Ladder разбивает диапазон на полные календарные единицы, получает каждый уровень один раз агрегацией следующего, более мелкого уровня и суммирует локально — число запросов зависит от крупных единиц, а не от минутных бакетов.",
      "hero.btn.github": "Смотреть на GitHub",
      "hero.btn.article": "Читать техническую статью",
      "hero.btn.disclosure": "Публичное раскрытие",
      "problem.title": "Запрос на 139 секунд",
      "problem.p1":
        "Рабочий запрос ThingsBoard через VPN занял <strong>139 секунд</strong> для 1 140 статистических бакетов. Арифметика была тривиальной; сеть — нет. Каждому бакету требовалось до четырёх HTTP-вызовов.",
      "problem.p2":
        "Очевидные решения — один крупный интервал, предварительная агрегация, пагинация — чем-то жертвуют: разрешением вывода, доступом на запись к источнику или числом сетевых обменов.",
      "problem.quote":
        "Полезный вопрос: может ли источник вернуть более крупную или более мелкую агрегацию по непрерывному участку, чтобы один запрос заполнил много выходных единиц?",
      "how.title": "Как это работает",
      "how.c1.title": "Разбить",
      "how.c1.body":
        "Разбейте диапазон на полные календарные единицы. Выводите только полные единицы; частичные левый и правый края передавайте на следующий, более мелкий уровень.",
      "how.c2.title": "Один запрос на уровень",
      "how.c2.body":
        "Получайте каждый максимальный непрерывный участок с общим уровнем выборки агрегацией следующего, более мелкого уровня: месяцы как дни, дни как часы, часы как минуты.",
      "how.c3.title": "Свернуть локально",
      "how.c3.body":
        "Просуммируйте полученные бакеты в выходные единицы. При необходимости разделите по локальному покрытию и получайте только непокрытые поддиапазоны.",
      "bench.title": "Измерено в production",
      "bench.scenario": "Сценарий",
      "bench.segments": "Сегменты",
      "bench.requests": "Запросы",
      "bench.time": "Время",
      "bench.r1": "2 дня, минуты",
      "bench.r2": "1 год, дни",
      "bench.r3": "10 месяцев, смешанные уровни",
      "bench.r4": "Локальное чтение, 42–90 сегментов",
      "bench.note":
        "Production-значения через VPN; задержка зависит от сети, нагрузки источника и плотности данных. Воспроизводимый бенчмарк печатает число сегментов и запросов без сервера.",
      "what.title": "Что это — и чем это не является",
      "what.is.title": "Это композиция планирования запросов",
      "what.is.li1": "календарная иерархия как план запроса, а не только как отображаемый бакет;",
      "what.is.li2": "выборка следующего, более мелкого уровня плюс локальная свёртка;",
      "what.is.li3": "группировка по уровню выборки и непрерывности;",
      "what.is.li4": "заполнение пробелов с учётом покрытия;",
      "what.is.li5": "число запросов ограничено лимитом бакетов на запрос источника.",
      "what.isnot.title": "Это не новая база данных и не новая теория",
      "what.isnot.li1": "RRDtool / Whisper: многомасштабные архивы;",
      "what.isnot.li2": "BTrDB: иерархические сводки, разделённые по времени;",
      "what.isnot.li3": "TimescaleDB: иерархические непрерывные агрегаты;",
      "what.isnot.li4": "Druid: гранулярность календарных периодов;",
      "what.isnot.li5": "Prometheus / Grafana: лимиты точек и одношаговый даунсэмплинг;",
      "what.isnot.li6": "деревья отрезков и timing wheels: выровненное разбиение и каскад уровней.",
      "what.note":
        "Метод опубликован как {disclosure} и распространяется по лицензии MIT. {prior} описывает ближайшие системы и отличия.",
      "cite.title": "Цитировать",
      "cite.note":
        "Архивировано в Zenodo: {zenodo}. Кнопка GitHub «Cite this repository» читает {citation}.",
      "try.title": "Попробовать",
      "try.note":
        "Демо не требует базы данных, сети и настройки. Документация: {readme} · {spec} · {zhArticle}.",
      "meta.title": "Hybrid Recursive Ladder — планирование запросов для API временных рядов с лимитом бакетов",
      "meta.description":
        "Агрегируйте длинные диапазоны временных рядов несколькими запросами вместо тысяч запросов по бакетам. Планировщик запросов календарного уровня для API с жёстким лимитом бакетов на запрос.",
    },

    ar: {
      "nav.github": "GitHub",
      "nav.algorithm": "الخوارزمية",
      "nav.prior": "الأعمال السابقة",
      "nav.article": "مقال",
      "nav.cite": "استشهاد",
      "hero.eyebrow": "تخطيط الاستعلامات لواجهات السلاسل الزمنية المحدودة بالدلاء",
      "hero.title": "جمّع النطاقات الطويلة <span>بعدد قليل من الطلبات</span>، لا بآلاف.",
      "hero.lead":
        "عميل الدلو الواحد يدفع رحلة شبكة واحدة لكل صف إخراج. تفكّك Hybrid Recursive Ladder النطاق إلى وحدات تقويمية كاملة، وتجلب كل مستوى مرة واحدة بتجميع المستوى الأدق، وتجمع محليًا — لذا يعتمد عدد الطلبات على الوحدات الخشنة، لا على دلاء الدقيقة.",
      "hero.btn.github": "عرض على GitHub",
      "hero.btn.article": "اقرأ المقال التقني",
      "hero.btn.disclosure": "إفصاح عام",
      "problem.title": "استعلام الـ 139 ثانية",
      "problem.p1":
        "استغرق استعلام ThingsBoard إنتاجي عبر VPN <strong>139 ثانية</strong> لـ 1,140 دلوًا إحصائيًا. كانت الحسابات بسيطة؛ الشبكة لم تكن كذلك. احتاج كل دلو إلى ما يصل إلى أربع مكالمات HTTP.",
      "problem.p2":
        "الحلول الواضحة — فاصل زمني خشن واحد، أو تجميع مسبق، أو ترقيم صفحات — تضحي بشيء: دقة الإخراج، أو إذن الكتابة إلى المصدر، أو عدد الرحلات.",
      "problem.quote":
        "السؤال المفيد: هل يمكن للمصدر إرجاع تجميع أخشن أو أدق على مقطع متصل، بحيث يملأ طلب واحد وحدات إخراج كثيرة؟",
      "how.title": "كيف يعمل",
      "how.c1.title": "التفكيك",
      "how.c1.body":
        "قسّم النطاق إلى وحدات تقويمية كاملة. أخرج الوحدات الكاملة فقط؛ وادفع الحواف الجزئية اليسرى واليمنى إلى المستوى الأدق.",
      "how.c2.title": "جلب مرة واحدة لكل مستوى",
      "how.c2.body":
        "اجلب كل مقطع متصل أقصى يشترك في مستوى الجلب بتجميع المستوى الأدق: الأشهر كأيام، والأيام كساعات، والساعات كدقائق.",
      "how.c3.title": "الجمع محليًا",
      "how.c3.body":
        "اجمع الدلاء المُعادة في وحدات الإخراج. اختياريًا قسّم حسب التغطية المحلية واجلب فقط النطاقات الفرعية غير المغطاة.",
      "bench.title": "قياس على نشر إنتاجي",
      "bench.scenario": "السيناريو",
      "bench.segments": "المقاطع",
      "bench.requests": "الطلبات",
      "bench.time": "الوقت",
      "bench.r1": "يومان، دقة الدقيقة",
      "bench.r2": "سنة، دقة اليوم",
      "bench.r3": "10 أشهر، مستويات مختلطة",
      "bench.r4": "قراءة محلية، 42–90 مقطعًا",
      "bench.note":
        "أرقام الإنتاج عبر VPN؛ تعتمد الكمون على الشبكة وحمل المصدر وكثافة البيانات. يطبع البنشمارك القابل للتكرار عدد المقاطع والطلبات دون خادم.",
      "what.title": "ما هو — وما ليس هو",
      "what.is.title": "هو تركيب لتخطيط الاستعلامات",
      "what.is.li1": "التسلسل التقويمي كخطة استعلام، وليس مجرد دلو عرض؛",
      "what.is.li2": "جلب المستوى الأدق مع الجمع المحلي؛",
      "what.is.li3": "التجميع حسب مستوى الجلب والاتصال الزمني؛",
      "what.is.li4": "ملء الفراغات مع مراعاة التغطية؛",
      "what.is.li5": "عدد الطلبات محدود بحد الدلاء لكل طلب في المصدر.",
      "what.isnot.title": "ليس قاعدة بيانات جديدة ولا نظرية جديدة",
      "what.isnot.li1": "RRDtool / Whisper: أرشيفات متعددة الدقة؛",
      "what.isnot.li2": "BTrDB: ملخصات هرمية مقسمة زمنيًا؛",
      "what.isnot.li3": "TimescaleDB: تجميعات مستمرة هرمية؛",
      "what.isnot.li4": "Druid: حبيبية فترات التقويم؛",
      "what.isnot.li5": "Prometheus / Grafana: حدود النقاط والاختزال بخطوة واحدة؛",
      "what.isnot.li6": "أشجار المقاطع وعجلات التوقيت: تفكيك محاذى وتتابع مستويات.",
      "what.note":
        "نُشرت الطريقة كـ{disclosure} وتُوزَّع بموجب ترخيص MIT. توثّق {prior} أقرب الأنظمة والاختلافات.",
      "cite.title": "استشهد بهذا العمل",
      "cite.note":
        "مؤرشف في Zenodo: {zenodo}. يقرأ زر GitHub «Cite this repository» ملف {citation}.",
      "try.title": "جرّبه",
      "try.note":
        "لا يحتاج العرض التجريبي إلى قاعدة بيانات أو شبكة أو إعداد. الوثائق: {readme} · {spec} · {zhArticle}.",
      "meta.title": "Hybrid Recursive Ladder — تخطيط الاستعلامات لواجهات السلاسل الزمنية المحدودة بالدلاء",
      "meta.description":
        "جمّع نطاقات طويلة من السلاسل الزمنية بعدد قليل من الطلبات بدلاً من آلاف الاستعلامات لكل دلو. مخطط استعلامات على مستوى التقويم لواجهات ذات حد صارم للدلاء لكل طلب.",
    },

    hi: {
      "nav.github": "GitHub",
      "nav.algorithm": "एल्गोरिद्म",
      "nav.prior": "पूर्व कार्य",
      "nav.article": "लेख",
      "nav.cite": "उद्धरण",
      "hero.eyebrow": "बकेट-सीमित टाइम-सीरीज़ API के लिए क्वेरी प्लानिंग",
      "hero.title": "लंबी रेंज को <span>मुट्ठी भर अनुरोधों</span> से एग्रीगेट करें, हज़ारों से नहीं।",
      "hero.lead":
        "प्रति-बकेट क्लाइंट हर आउटपुट पंक्ति के लिए एक नेटवर्क राउंड-ट्रिप देता है। Hybrid Recursive Ladder रेंज को पूर्ण कैलेंडर इकाइयों में विभाजित करता है, हर स्तर को अगले महीन एग्रीगेशन से एक बार लाता है और स्थानीय रूप से जोड़ता है — इसलिए अनुरोधों की संख्या मिनट-बकेट पर नहीं, मोटी इकाइयों पर निर्भर करती है।",
      "hero.btn.github": "GitHub पर देखें",
      "hero.btn.article": "तकनीकी लेख पढ़ें",
      "hero.btn.disclosure": "सार्वजनिक प्रकटीकरण",
      "problem.title": "139 सेकंड की क्वेरी",
      "problem.p1":
        "VPN के ज़रिए एक प्रोडक्शन ThingsBoard क्वेरी ने 1,140 सांख्यिकीय बकेट के लिए <strong>139 सेकंड</strong> लिए। गणित सरल था; नेटवर्क नहीं। हर बकेट को चार HTTP कॉल तक चाहिए थे।",
      "problem.p2":
        "स्पष्ट समाधान — एक मोटा interval, पूर्व-एग्रीगेशन, पेजिनेशन — कुछ न कुछ त्यागते हैं: आउटपुट रिज़ॉल्यूशन, स्रोत पर लिखने की पहुँच, या राउंड-ट्रिप की संख्या।",
      "problem.quote":
        "उपयोगी सवाल: क्या स्रोत किसी सतत हिस्से पर अधिक मोटा या महीन एग्रीगेशन एक बार में लौटा सकता है, ताकि एक अनुरोध कई आउटपुट इकाइयाँ भर दे?",
      "how.title": "यह कैसे काम करता है",
      "how.c1.title": "विभाजित करें",
      "how.c1.body":
        "रेंज को पूर्ण कैलेंडर इकाइयों में बाँटें। केवल पूर्ण इकाइयाँ आउटपुट करें; बाएँ और दाएँ आंशिक किनारे अगले महीन स्तर पर भेजें।",
      "how.c2.title": "प्रति स्तर एक बार लाएँ",
      "how.c2.body":
        "समान फ़ेच-स्तर वाले सबसे बड़े सतत हिस्से को अगले महीन एग्रीगेशन से एक बार लाएँ: महीने दिनों के रूप में, दिन घंटों के रूप में, घंटे मिनटों के रूप में।",
      "how.c3.title": "स्थानीय रूप से जोड़ें",
      "how.c3.body":
        "लौटाए गए बकेट को आउटपुट इकाइयों में जोड़ें। वैकल्पिक रूप से स्थानीय कवरेज के अनुसार विभाजित करें और केवल बिना कवरेज वाले उप-हिस्से लाएँ।",
      "bench.title": "प्रोडक्शन डिप्लॉयमेंट पर मापा गया",
      "bench.scenario": "परिदृश्य",
      "bench.segments": "सेगमेंट",
      "bench.requests": "अनुरोध",
      "bench.time": "समय",
      "bench.r1": "2 दिन, मिनट स्तर",
      "bench.r2": "1 वर्ष, दिन स्तर",
      "bench.r3": "10 महीने, मिश्रित स्तर",
      "bench.r4": "स्थानीय रीड, 42–90 सेगमेंट",
      "bench.note":
        "प्रोडक्शन आंकड़े VPN पर; विलंब नेटवर्क, स्रोत लोड और डेटा घनत्व पर निर्भर करता है। पुनरुत्पादनीय बेंचमार्क बिना सर्वर के सेगमेंट और अनुरोध संख्या छापता है।",
      "what.title": "यह क्या है—और क्या नहीं",
      "what.is.title": "यह क्वेरी-प्लानिंग संयोजन है",
      "what.is.li1": "कैलेंडर पदानुक्रम को क्वेरी योजना के रूप में, केवल डिस्प्ले बकेट के रूप में नहीं;",
      "what.is.li2": "अगला महीन स्तर लाना और स्थानीय जोड़;",
      "what.is.li3": "फ़ेच-स्तर + निरंतरता समूहन;",
      "what.is.li4": "कवरेज-जागरूक गैप भरना;",
      "what.is.li5": "अनुरोध संख्या स्रोत की प्रति-अनुरोध बकेट सीमा से बंधी।",
      "what.isnot.title": "यह नया डेटाबेस या नया सिद्धांत नहीं है",
      "what.isnot.li1": "RRDtool / Whisper: बहु-रिज़ॉल्यूशन अभिलेख;",
      "what.isnot.li2": "BTrDB: समय-विभाजित पदानुक्रमित सारांश;",
      "what.isnot.li3": "TimescaleDB: पदानुक्रमित सतत एग्रीगेट;",
      "what.isnot.li4": "Druid: कैलेंडर अवधि ग्रैन्युलैरिटी;",
      "what.isnot.li5": "Prometheus / Grafana: पॉइंट सीमा और एक-चरण डाउनसैंपलिंग;",
      "what.isnot.li6": "सेगमेंट ट्री और टाइमिंग व्हील: संरेखित विभाजन और स्तर कैस्केड।",
      "what.note":
        "यह विधि {disclosure} के रूप में प्रकाशित है और MIT लाइसेंस के अंतर्गत है। {prior} निकटतम प्रणालियों और अंतरों को प्रलेखित करती है।",
      "cite.title": "इस कार्य को उद्धृत करें",
      "cite.note":
        "Zenodo में संग्रहीत: {zenodo}. GitHub का “Cite this repository” बटन {citation} पढ़ता है।",
      "try.title": "आज़माएँ",
      "try.note":
        "डेमो के लिए डेटाबेस, नेटवर्क या कॉन्फ़िगरेशन की आवश्यकता नहीं। दस्तावेज़: {readme} · {spec} · {zhArticle}.",
      "meta.title": "Hybrid Recursive Ladder — बकेट-सीमित टाइम-सीरीज़ API के लिए क्वेरी प्लानिंग",
      "meta.description":
        "हज़ारों प्रति-बकेट क्वेरी के बजाय मुट्ठी भर अनुरोधों से लंबी टाइम-सीरीज़ रेंज एग्रीगेट करें। प्रति-अनुरोध बकेट की कड़ी सीमा वाले API के लिए कैलेंडर-स्तरीय क्वेरी प्लानर।",
    },
  };

  const SUPPORTED = Object.keys(I18N);
  const select = document.getElementById("lang-select");
  if (!select) return;

  function renderTemplate(template, lang) {
    const labels = Object.assign({}, STATIC_LINK_TEXT, LINK_TEXT[lang] || LINK_TEXT.en);
    return template.replace(/\{(\w+)\}/g, (match, key) => {
      if (LINK_URLS[key] && labels[key]) {
        return `<a href="${LINK_URLS[key]}">${labels[key]}</a>`;
      }
      return match;
    });
  }

  function apply(lang) {
    const dict = I18N[lang] || I18N.en;
    const t = (key) => (dict[key] != null ? dict[key] : I18N.en[key]);

    document.querySelectorAll("[data-i18n]").forEach((el) => {
      const value = t(el.getAttribute("data-i18n"));
      if (value != null) el.textContent = value;
    });
    document.querySelectorAll("[data-i18n-html]").forEach((el) => {
      const value = t(el.getAttribute("data-i18n-html"));
      if (value != null) el.innerHTML = renderTemplate(value, lang);
    });

    document.documentElement.lang = lang;
    document.documentElement.dir = lang === "ar" ? "rtl" : "ltr";

    const title = t("meta.title");
    const description = t("meta.description");
    if (title) document.title = title;
    if (description) {
      const desc = document.getElementById("page-description");
      const ogDesc = document.getElementById("og-description");
      if (desc) desc.setAttribute("content", description);
      if (ogDesc) ogDesc.setAttribute("content", description);
    }
    if (title) {
      const ogTitle = document.getElementById("og-title");
      if (ogTitle) ogTitle.setAttribute("content", title);
    }

    select.value = lang;
    try {
      localStorage.setItem("hrl-lang", lang);
    } catch (_) {
      /* private mode: ignore */
    }

    try {
      const url = new URL(window.location.href);
      if (lang === "en") url.searchParams.delete("lang");
      else url.searchParams.set("lang", lang);
      history.replaceState(null, "", url);
    } catch (_) {
      /* file:// or restricted history: ignore */
    }
  }

  function normalize(tag) {
    if (!tag) return "en";
    const lower = tag.toLowerCase();
    if (lower.startsWith("zh")) return "zh-CN";
    if (lower.startsWith("pt")) return "pt-BR";
    const base = lower.split("-")[0];
    return SUPPORTED.includes(base) ? base : "en";
  }

  let stored = null;
  try {
    stored = localStorage.getItem("hrl-lang");
  } catch (_) {
    /* private mode: ignore */
  }
  const queryLang = new URLSearchParams(window.location.search).get("lang");
  const initial =
    queryLang && SUPPORTED.includes(queryLang)
      ? queryLang
      : stored && SUPPORTED.includes(stored)
        ? stored
        : normalize(navigator.language);

  select.addEventListener("change", () => apply(select.value));
  apply(initial);
})();
