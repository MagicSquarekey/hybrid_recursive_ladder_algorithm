# خوارزمية السلّم التكراري الهجينة (Hybrid Recursive Ladder Algorithm)

**جمّع نطاقات زمنية طويلة من السلاسل الزمنية بعدد قليل من الطلبات بدلاً من آلاف الاستعلامات لكل دلو.**

**اللغات / Languages:** [English](README.md) · [简体中文](README.zh-CN.md) · [日本語](README.ja.md) · [한국어](README.ko.md) · [Español](README.es.md) · [Français](README.fr.md) · [Deutsch](README.de.md) · [Português](README.pt-BR.md) · [Русский](README.ru.md) · [العربية](README.ar.md) · [हिन्दी](README.hi.md)

[![CI](https://github.com/MagicSquarekey/hybrid_recursive_ladder_algorithm/actions/workflows/ci.yml/badge.svg)](https://github.com/MagicSquarekey/hybrid_recursive_ladder_algorithm/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Version](https://img.shields.io/badge/version-0.0.3-green.svg)](CHANGELOG.md)
[![Website](https://img.shields.io/badge/website-live-5eead4.svg)](https://magicsquarekey.github.io/hybrid_recursive_ladder_algorithm/)
[![DOI](https://zenodo.org/badge/DOI/10.5281/zenodo.23556606.svg)](https://doi.org/10.5281/zenodo.23556606)

<p align="center">
  <img src="docs/assets/hero.png" alt="Per-bucket client versus calendar ladder" width="100%">
</p>

<p align="center"><em>نفس الناتج. عدد طلبات مختلف تمامًا.</em></p>

## المشكلة

معظم واجهات السلاسل الزمنية تحاسب على عدد الطلبات أو الدلاء أو رحلات الشبكة. التنفيذ الساذج («استعلام واحد لكل دلو إحصائي») يحوّل نطاق يومين بدقة الدقيقة إلى 2,880 دلوًا، كل دلو يحتاج حتى أربع مكالمات HTTP. في نشر ThingsBoard حقيقي استغرق 1,140 دلوًا **139 ثانية**.

عنق الزجاجة ليس الحساب، بل عدد رحلات الشبكة.

## الفكرة

يُقسَّم `[start, end)` إلى **وحدات تقويمية كاملة** من الشهر إلى الدقيقة. تُزال الأشهر الكاملة أولاً، وتُدفع الأطراف الجزئية إلى المستوى الأدق، ويصبح الباقي الأقل من دقيقة «ذيلاً» مستقلاً. ثم يُجلب كل مستوى مرة واحدة بتجميع المستوى الأدق، ويُجمع محليًا.

```
2026-01-01 00:00:00 → 2026-10-21 18:49:59

شهر    2026-01 … 2026-09          9 مقاطع
يوم    10-01 … 10-20             20 مقطعًا
ساعة   10-21 00:00 … 17:00       18 مقطعًا
دقيقة  10-21 18:00 … 18:48       49 مقطعًا
ذيل    10-21 18:49:00–18:49:59    1 مقطع
                                  ───────────
                                  97 مقطعًا
```

**97 مقطعًا بدلاً من 423,049 دلوًا دقيقيًا** (تقليل بنحو 4,360 مرة). الاستعلام النموذجي لـ 10 أشهر يحتاج **5–7 طلبات تجميع** فقط، وليس آلافًا.

## التثبيت

```bash
# v0.0.3 GitHub release wheel
pip install https://github.com/MagicSquarekey/hybrid_recursive_ladder_algorithm/releases/download/v0.0.3/hybrid_recursive_ladder-0.0.3-py3-none-any.whl

# optional extras: clone and install
git clone https://github.com/MagicSquarekey/hybrid_recursive_ladder_algorithm.git
cd hybrid_recursive_ladder_algorithm
```

إضافات اختيارية:

```bash
pip install -e ".[thingsboard]"
pip install -e ".[postgres]"
pip install -e ".[api]"
pip install -e ".[mcp]"
pip install -e ".[all]"
```

لا يعتمد جوهر التقسيم على أي طرف ثالث (فقط `tzdata` للمناطق الزمنية IANA).

## عرض سريع في 30 ثانية

```bash
hybrid-ladder demo
```

يولّد بيانات تركيبية كل 15 دقيقة، ويقسّم 120 يومًا، ويجسّد أول 90 يومًا في مخزن بالذاكرة، ويشغّل استعلامًا هجينًا «محلي أولاً»، ويتحقق من تطابق الإجماليات. دون قاعدة بيانات أو شبكة أو إعدادات.

```bash
hybrid-ladder decompose --start 2026-01-01 --end 2026-10-21T18:49:59
```

## المكتبة

```python
from hybrid_ladder import LadderEngine, MemorySource

source = MemorySource()
source.add("device-1", "energy", [(ts, 1.0) for ts in range(0, 86_400_000, 60_000)])

engine = LadderEngine(source)
result = engine.sum([("device-1", "energy")], 0, 86_400_000)

print(result.grand_total)                 # 1440.0
print(result.rows[0].segments[0].label)   # 1970-01-01 08:00
```

مع مخزن محلي:

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

## خمس طرق للاستخدام

| الشكل | نقطة الدخول | الاستخدام |
|---|---|---|
| مكتبة Python | `from hybrid_ladder import ...` | التضمين في خدمة أو خط بيانات |
| سطر الأوامر | `hybrid-ladder ...` | فحص سريع، سكربتات، cron |
| واجهة HTTP | `hybrid-ladder serve` | تكامل بأي لغة، مهام غير متزامنة |
| خادم MCP | `hybrid-ladder mcp` | وكلاء الذكاء الاصطناعي وعملاء MCP |
| مهارة وكيل | [`skills/hybrid-recursive-ladder/SKILL.md`](skills/hybrid-recursive-ladder/SKILL.md) | التثبيت كمهارة |

```bash
hybrid-ladder serve --port 8000     # OpenAPI: http://127.0.0.1:8000/docs
hybrid-ladder mcp                   # خادم MCP عبر stdio
```

## القواعد (غير قابلة للتفاوض)

1. **فترة مغلقة من اليسار ومفتوحة من اليمين** `[start, end)`. إذا وقع النهاية على حدّ بالضبط، فلا وجود لتلك الوحدة في النتيجة.
2. **الوحدات الكاملة فقط**. لا يُخرَج الشهر/اليوم/الساعة/الدقيقة في مستواه إلا إذا كان داخل النطاق بالكامل.
3. **الأطراف متكررة**. الأطراف الجزئية تنتقل إلى المستوى الأدق، والباقي الأقل من دقيقة يصبح ذيلاً مستقلاً.
4. **التقويم المحلي**. تُحسب الحدود بالمنطقة الزمنية IANA المحددة (الافتراضي `Asia/Shanghai`).
5. **ثبات التغطية**. المقاطع مرتبة ومتجاورة وغير متداخلة، واتحادها يساوي `[start, end)` تمامًا.

## دلالات القيم

| القيمة | المعنى | العرض |
|---|---|---|
| `null` | لا توجد قياسات | `—` |
| `0.0` | توجد قياسات ومجموعها صفر | `0` |
| رقم | مجموع القياسات | الرقم |

كل مقطع يحمل `cnt` (النقاط/الدلاء المرصودة)، و`expected` (الدلاء المتوقعة، لمقاطع المصدر فقط)، و`source` (`local` / `tb` / `mixed` / `empty` / `uncovered`). انخفاض `cnt` عن `expected` يعني بيانات متفرقة؛ المجموع صحيح للنقاط الموجودة، ولا يتم تعويض الناقص.

## المحولات

يعتمد المحرك على واجهتين هيكليتين صغيرتين فقط:

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

المضمّن: `MemorySource` / `MemoryStore`، `ThingsBoardSource`، `PostgresStore`. أي مصدر مثل InfluxDB أو Prometheus أو ClickHouse يحتاج فقط إلى هذه الطرق.

## القراءة المحلية أولاً، والتحقق، والإصلاح

* تُسجَّل التغطية حتى `now - 5 دقائق` فقط؛ الذيل الجاري لا يُعدّ أبدًا بيانات محلية موثوقة.
* يُسجَّل النطاق الذي تم استعلامه حتى لو كان صفر نقاط («سألنا ولا توجد بيانات») لتجنب إعادة الطلب.
* قبل إعادة كتابة نطاق تُمسح تغطيته: فشل في المنتصف لا يترك تغطية تشير إلى بيانات ناقصة.
* `verify` يقارن المصدر (المرجع) بالمخزن المحلي مقطعًا بمقطع، ولا ينزل إلى مستوى النقاط (`added`/`removed`/`changed`) إلا للمقاطع المختلفة.
* `repair` يحذف النطاق المحلي ويعيد جلبه من المصدر؛ النقاط المحذوفة في المصدر تختفي محليًا.

## القيود

* الإصدار v0.0.3 ينفّذ `sum` فقط. `avg` يحتاج ترجيحًا؛ `meter_delta` يحتاج أول قيمة في كل مقطع.
* نقص القياسات يجعل الإجمالي أقل من الإجمالي الفيزيائي. `cnt/expected` يكشفان ذلك دون تعويض.
* ThingsBoard يقبل نحو 700 دلو ويرفض 800؛ الافتراضي 500.
* المهام الخلفية تعيش في ذاكرة العملية وتُفقد عند إعادة التشغيل (يمكن إعادة حساب النتائج).
* بسبب أحجام الدلاء الثابتة، طيّ اليوم/الساعة مصمم للمناطق ذات الإزاحة الثابتة مثل `Asia/Shanghai`.

## الأداء (مقاس)

| السيناريو | المقاطع | الطلبات | الوقت |
|---|---:|---:|---:|
| يومان، دقة الدقيقة | 69 | ~4 | 0.64 ث |
| سنة، دقة اليوم | 42 | ~4 | 1.18 ث بارد / 0.20 ث ساخن |
| 10 أشهر، مستويات مختلطة | 97 | ~5–7 | أقل من ثانية |
| قراءة محلية | 42–90 | 0 | 9–19 مللي ثانية |

أعد إنتاج عدد المقاطع والطلبات دون شبكة:

```bash
python examples/benchmark.py
```

## الوثائق

* [مواصفات الخوارزمية](docs/algorithm.md)
* [البنية المعمارية](docs/architecture.md)
* [مرجع API](docs/api.md)
* [القياسات](docs/benchmarks.md)
* [الأعمال ذات الصلة والتموضع](docs/related-work.md)

## الترخيص

[MIT](LICENSE) © 2026 MagicSquarekey
