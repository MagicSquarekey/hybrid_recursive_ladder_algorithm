# हाइब्रिड रिकर्सिव लैडर एल्गोरिद्म (Hybrid Recursive Ladder Algorithm)

**हज़ारों प्रति-बकेट क्वेरी के बजाय मुट्ठी भर स्रोत रिक्वेस्ट से लंबी टाइम-सीरीज़ रेंज को एग्रीगेट करें।**

**भाषाएँ / Languages:** [English](README.md) · [简体中文](README.zh-CN.md) · [日本語](README.ja.md) · [한국어](README.ko.md) · [Español](README.es.md) · [Français](README.fr.md) · [Deutsch](README.de.md) · [Português](README.pt-BR.md) · [Русский](README.ru.md) · [العربية](README.ar.md) · [हिन्दी](README.hi.md)

[![CI](https://github.com/MagicSquarekey/hybrid_recursive_ladder_algorithm/actions/workflows/ci.yml/badge.svg)](https://github.com/MagicSquarekey/hybrid_recursive_ladder_algorithm/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Version](https://img.shields.io/badge/version-0.0.5-green.svg)](CHANGELOG.md)
[![Website](https://img.shields.io/badge/website-live-5eead4.svg)](https://magicsquarekey.github.io/hybrid_recursive_ladder_algorithm/)
[![DOI](https://zenodo.org/badge/DOI/10.5281/zenodo.23557574.svg)](https://doi.org/10.5281/zenodo.23557574)

<p align="center">
  <img src="docs/assets/hero.hi.png" alt="Per-bucket client versus calendar ladder" width="100%">
</p>

<p align="center"><em>वही आउटपुट। बहुत अलग अनुरोध संख्या।</em></p>

## समस्या

अधिकांश टाइम-सीरीज़ API प्रति रिक्वेस्ट, प्रति बकेट या प्रति नेटवर्क राउंड-ट्रिप शुल्क लेते हैं। "हर सांख्यिकीय बकेट के लिए एक क्वेरी" वाला सीधा कार्यान्वयन दो दिन की मिनट-स्तरीय रेंज को 2,880 बकेट में बदल देता है, हर बकेट के लिए चार HTTP कॉल तक। एक प्रोडक्शन ThingsBoard डिप्लॉयमेंट में 1,140 बकेट में **139 सेकंड** लगे।

अड़चन गणित नहीं, नेटवर्क राउंड-ट्रिप की संख्या है।

## विचार

`[start, end)` को **पूर्ण कैलेंडर इकाइयों** (महीना → दिन → घंटा → मिनट) में पुनरावर्ती रूप से विभाजित करें। पूरे महीने पहले हटाए जाते हैं; आंशिक किनारे अगले महीन स्तर पर भेजे जाते हैं; सबसे महीन स्तर पर एक मिनट से कम का शेष अपना अलग "टेल" सेगमेंट बनता है। फिर हर स्तर को अगले महीन स्तर के एग्रीगेशन से एक बार लाया जाता है और स्थानीय रूप से जोड़ा जाता है।

```
2026-01-01 00:00:00 → 2026-10-21 18:49:59

महीना  2026-01 … 2026-09          9 सेगमेंट
दिन     10-01 … 10-20             20 सेगमेंट
घंटा    10-21 00:00 … 17:00       18 सेगमेंट
मिनट    10-21 18:00 … 18:48       49 सेगमेंट
टेल     10-21 18:49:00–18:49:59    1 सेगमेंट
                                  ───────────
                                  97 सेगमेंट
```

**423,049 मिनट-बकेट के बजाय 97 सेगमेंट** (लगभग 4,360 गुना कम)। 10 महीने की सामान्य क्वेरी में **5–7 एग्रीगेशन रिक्वेस्ट** ही लगती हैं, हज़ारों नहीं।

## इंस्टॉलेशन

```bash
# v0.0.5 GitHub release wheel
pip install https://github.com/MagicSquarekey/hybrid_recursive_ladder_algorithm/releases/download/v0.0.5/hybrid_recursive_ladder-0.0.5-py3-none-any.whl

# optional extras: clone and install
git clone https://github.com/MagicSquarekey/hybrid_recursive_ladder_algorithm.git
cd hybrid_recursive_ladder_algorithm
```

वैकल्पिक एक्सट्रा:

```bash
pip install -e ".[thingsboard]"
pip install -e ".[postgres]"
pip install -e ".[api]"
pip install -e ".[mcp]"
pip install -e ".[all]"
```

कोर विभाजन में कोई तीसरे पक्ष की निर्भरता नहीं है (केवल IANA टाइमज़ोन के लिए `tzdata`)।

## 30-सेकंड डेमो

```bash
hybrid-ladder demo
```

सिंथेटिक 15-मिनट डेटा बनाता है, 120 दिन विभाजित करता है, पहले 90 दिन को इन-मेमोरी स्टोर में मटेरियलाइज़ करता है, लोकल-फर्स्ट मिक्स्ड क्वेरी चलाता है और कुल योग मिलने की पुष्टि करता है। डेटाबेस, नेटवर्क या कॉन्फ़िगरेशन की ज़रूरत नहीं।

```bash
hybrid-ladder decompose --start 2026-01-01 --end 2026-10-21T18:49:59
```

## लाइब्रेरी

```python
from hybrid_ladder import LadderEngine, MemorySource

source = MemorySource()
source.add("device-1", "energy", [(ts, 1.0) for ts in range(0, 86_400_000, 60_000)])

engine = LadderEngine(source)
result = engine.sum([("device-1", "energy")], 0, 86_400_000)

print(result.grand_total)                 # 1440.0
print(result.rows[0].segments[0].label)   # 1970-01-01 08:00
```

लोकल स्टोर के साथ:

```python
from hybrid_ladder import LadderEngine
from hybrid_ladder.sources.thingsboard import ThingsBoardSource
from hybrid_ladder.stores.postgres import PostgresStore

source = ThingsBoardSource("https://tb.example.com", token="...")
store = PostgresStore("postgresql://user:pass@127.0.0.1:5432/telemetry")
engine = LadderEngine(source, store)

engine.materialize([("device-id", "energy")], start_ms, end_ms)
result = engine.sum_mixed([("device-id", "energy")], start_ms, end_ms)
print(result.source, result.source_counts, result.rows[0].tb_ranges)

report = engine.verify([("device-id", "energy")], start_ms, end_ms)
if report["diff_segments"]:
    engine.repair([("device-id", "energy")], start_ms, end_ms)
```

## उपयोग के पाँच रूप

| रूप | एंट्री पॉइंट | उपयोग |
|---|---|---|
| Python लाइब्रेरी | `from hybrid_ladder import ...` | सेवा या पाइपलाइन में एम्बेड |
| CLI | `hybrid-ladder ...` | जाँच, स्क्रिप्ट, cron |
| HTTP API | `hybrid-ladder serve` | भाषा-स्वतंत्र एकीकरण, असिंक्रोनस टास्क |
| MCP सर्वर | `hybrid-ladder mcp` | AI एजेंट / MCP क्लाइंट |
| एजेंट स्किल | [`skills/hybrid-recursive-ladder/SKILL.md`](skills/hybrid-recursive-ladder/SKILL.md) | स्किल के रूप में इंस्टॉल |

```bash
hybrid-ladder serve --port 8000     # OpenAPI: http://127.0.0.1:8000/docs
hybrid-ladder mcp                   # stdio पर MCP सर्वर
```

## नियम (अनिवार्य)

1. **बायाँ बंद, दायाँ खुला** `[start, end)`। यदि अंत ठीक किसी सीमा पर है, तो वह इकाई परिणाम में नहीं होती।
2. **केवल पूर्ण इकाइयाँ**। महीना/दिन/घंटा/मिनट अपने स्तर पर तभी आता है जब वह पूरी तरह रेंज के अंदर हो।
3. **किनारे पुनरावर्ती**। आंशिक बाएँ/दाएँ किनारे अगले महीन स्तर पर जाते हैं; एक मिनट से कम शेष अलग टेल बनता है।
4. **स्थानीय कैलेंडर**। सीमाएँ कॉन्फ़िगर किए गए IANA टाइमज़ोन (डिफ़ॉल्ट `Asia/Shanghai`) में गणना की जाती हैं।
5. **टाइलिंग इनवेरिएंट**। सेगमेंट क्रम में, सटे हुए, बिना ओवरलैप के होते हैं और उनका संघ ठीक `[start, end)` होता है।

## मान का अर्थ

| मान | अर्थ | प्रदर्शन |
|---|---|---|
| `null` | कोई सैंपल नहीं | `—` |
| `0.0` | सैंपल हैं और योग शून्य है | `0` |
| संख्या | सैंपल का योग | संख्या |

हर सेगमेंट में `cnt` (देखे गए पॉइंट/बकेट), `expected` (अपेक्षित बकेट, केवल स्रोत सेगमेंट) और `source` (`local` / `tb` / `mixed` / `empty` / `uncovered`) होता है। `expected` की तुलना में कम `cnt` डेटा के विरल होने का संकेत है; योग मौजूद पॉइंट के लिए सही रहता है, डेटा भरा नहीं जाता।

## एडाप्टर

इंजन केवल दो छोटे ढाँचागत इंटरफ़ेस पर निर्भर करता है:

```python
class TimeSeriesSource(Protocol):
    def interval_agg(ref, start_ms, end_ms, bucket_ms, agg="SUM") -> Mapping[int, Any]: ...
    def raw_series(ref, start_ms, end_ms, limit=10_000) -> list[tuple[int, Any]]: ...

class PointStore(Protocol):
    def sum_ranges(ref, ranges) -> Mapping[int, tuple[float | None, int]]: ...
    def series(ref, start_ms, end_ms, max_points=5_000) -> list[Mapping]: ...
    def coverage(ref) -> list[tuple[int, int, int]]: ...
    def delete_range(ref, start_ms, end_ms) -> int: ...
    def clear_coverage(ref, start_ms, end_ms) -> int: ...
    def upsert_points(ref, points, at_ms=None) -> int: ...
    def mark_covered(ref, start_ms, end_ms, point_cnt, at_ms) -> None: ...
```

अंतर्निहित: `MemorySource` / `MemoryStore`, `ThingsBoardSource`, `PostgresStore`. InfluxDB, Prometheus या ClickHouse के लिए केवल ये मेथड लागू करने हैं।

## लोकल-फर्स्ट, सत्यापन और मरम्मत

* कवरेज केवल `now - 5 मिनट` तक दर्ज होती है; चल रहा टेल कभी भरोसेमंद लोकल डेटा नहीं माना जाता।
* क्वेरी की गई रेंज शून्य पॉइंट होने पर भी दर्ज होती है ("हमने पूछा, कुछ नहीं है"), ताकि दोबारा स्रोत पर न जाएँ।
* रेंज दोबारा लिखने से पहले उसकी कवरेज मिटाई जाती है: बीच में विफलता होने पर अधूरे डेटा की कवरेज नहीं बचती।
* `verify` स्रोत (प्रामाणिक) की तुलना लोकल स्टोर से सेगमेंट-दर-सेगमेंट करता है और केवल अलग सेगमेंट में पॉइंट स्तर (`added`/`removed`/`changed`) तक जाता है।
* `repair` लोकल रेंज हटाकर स्रोत से फिर लाता है; स्रोत में हटाए गए पॉइंट लोकल से भी हट जाते हैं।

## सीमाएँ

* v0.0.5 में केवल `sum` है। `avg` के लिए भारांकन चाहिए; `meter_delta` के लिए हर सेगमेंट का पहला मान चाहिए।
* डेटा छूटने पर कुल योग भौतिक कुल से कम होगा। `cnt/expected` इसे दिखाते हैं, भरपाई नहीं करते।
* ThingsBoard लगभग 700 बकेट स्वीकारता है और 800 अस्वीकारता है; डिफ़ॉल्ट 500 है।
* बैकग्राउंड टास्क प्रोसेस मेमोरी में रहते हैं और रीस्टार्ट पर चले जाते हैं (परिणाम दोबारा गणना योग्य)।
* निश्चित बकेट आकार के कारण दिन/घंटा फोल्डिंग `Asia/Shanghai` जैसे स्थिर ऑफ़सेट वाले टाइमज़ोन के लिए है।

## प्रदर्शन (मापा गया)

| परिदृश्य | सेगमेंट | रिक्वेस्ट | समय |
|---|---:|---:|---:|
| 2 दिन, मिनट स्तर | 69 | ~4 | 0.64 सेकंड |
| 1 वर्ष, दिन स्तर | 42 | ~4 | 1.18 सेकंड ठंडा / 0.20 सेकंड गर्म |
| 10 महीने, मिश्रित | 97 | ~5–7 | एक सेकंड से कम |
| लोकल रीड | 42–90 | 0 | 9–19 मिलीसेकंड |

नेटवर्क के बिना सेगमेंट/रिक्वेस्ट संख्या दोबारा देखें:

```bash
python examples/benchmark.py
```

## दस्तावेज़

* [एल्गोरिद्म विनिर्देश](docs/algorithm.md)
* [आर्किटेक्चर](docs/architecture.md)
* [API संदर्भ](docs/api.md)
* [बेंचमार्क](docs/benchmarks.md)
* [संबंधित कार्य और स्थिति](docs/related-work.md)

## लाइसेंस

[MIT](LICENSE) © 2026 MagicSquarekey
