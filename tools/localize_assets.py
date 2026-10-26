#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Localize the README diagrams and render them to PNG.

The English assets in ``docs/assets`` are the source of truth.  For each
target language this script rewrites the ``<text>``, ``<title>`` and ``<desc>``
nodes, writes ``docs/assets/<name>.<lang>.svg``, and renders a 2x PNG beside
it with headless Chrome.

Run from the repository root::

    python tools/localize_assets.py              # every localized asset
    python tools/localize_assets.py --lang zh-CN # one language
    python tools/localize_assets.py --check      # report missing translations

Chrome is located through ``CHROME_PATH`` or the usual Windows install paths.
The English assets were produced with the same pipeline, so re-rendering
``hero.svg`` reproduces the committed ``hero.png`` byte for byte.
"""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
import tempfile
import xml.etree.ElementTree as ET
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
ASSETS = ROOT / "docs" / "assets"
SVG_NS = "http://www.w3.org/2000/svg"
ET.register_namespace("", SVG_NS)

# name -> (width, height) of the SVG canvas
IMAGES = {
    "hero": (1200, 640),
    "decomposition": (1200, 640),
    "architecture": (1200, 700),
}

# Images that each language actually ships.  The short READMEs only embed the
# hero diagram, so only hero is rendered for them.
LANG_IMAGES = {
    "zh-CN": ("hero", "decomposition", "architecture"),
    "ja": ("hero",),
    "ko": ("hero",),
    "es": ("hero",),
    "fr": ("hero",),
    "de": ("hero",),
    "pt-BR": ("hero",),
    "ru": ("hero",),
    "ar": ("hero",),
    "hi": ("hero",),
}

LATIN_SANS = "'Segoe UI', Roboto, Helvetica, Arial, sans-serif"
LATIN_MONO = "Consolas, 'Courier New', monospace"

# lang -> (sans stack, mono stack, right-to-left?)
LANGS = {
    "zh-CN": ("'Noto Sans SC', 'Microsoft YaHei', sans-serif", "'Noto Sans SC', Consolas, monospace", False),
    "ja": ("'Yu Gothic UI', 'Meiryo', sans-serif", "'Yu Gothic UI', Consolas, monospace", False),
    "ko": ("'Malgun Gothic', 'Gulim', sans-serif", "'Malgun Gothic', Consolas, monospace", False),
    "es": (LATIN_SANS, LATIN_MONO, False),
    "fr": (LATIN_SANS, LATIN_MONO, False),
    "de": (LATIN_SANS, LATIN_MONO, False),
    "pt-BR": (LATIN_SANS, LATIN_MONO, False),
    "ru": (LATIN_SANS, LATIN_MONO, False),
    "ar": ("'Segoe UI', Tahoma, Arial, sans-serif", "'Segoe UI', Tahoma, Consolas, monospace", True),
    "hi": ("'Nirmala UI', Mangal, sans-serif", "'Nirmala UI', Mangal, Consolas, monospace", False),
}


def _t(zh_cn, ja, ko, es, fr, de, pt_br, ru, ar, hi):
    """Build a per-language mapping.  Omitted languages fall back to English."""
    return {
        "zh-CN": zh_cn,
        "ja": ja,
        "ko": ko,
        "es": es,
        "fr": fr,
        "de": de,
        "pt-BR": pt_br,
        "ru": ru,
        "ar": ar,
        "hi": hi,
    }


# --------------------------------------------------------------------------
# Translations: English source text -> per-language rendering.
# Numbers, "API", "[start, end)" and clock labels are left untranslated.
# --------------------------------------------------------------------------
TRANSLATIONS: dict[str, dict[str, str]] = {
    # ---------------------------------------------------------------- hero
    "Per-bucket queries versus the calendar ladder": _t(
        "逐桶查询与日历阶梯对比",
        "バケット単位クエリとカレンダーラダーの比較",
        "버킷별 쿼리와 달력 사다리 비교",
        "Consultas por bucket frente a la escalera de calendario",
        "Requêtes par compartiment face à l'échelle calendaire",
        "Abfragen pro Bucket versus Kalenderleiter",
        "Consultas por bucket versus a escada de calendário",
        "Запросы по бакетам против календарной лестницы",
        "استعلامات لكل دلو مقابل سلّم التقويم",
        "प्रति-बकेट क्वेरी बनाम कैलेंडर लैडर",
    ),
    "Left: 1,140 buckets each needing up to four HTTP calls, taking 139 seconds. "
    "Right: 97 calendar segments fetched in about five to seven requests, taking 0.64 seconds.": _t(
        "左：1,140 个桶，每桶最多 4 次 HTTP 调用，耗时 139 秒。右：97 个日历段，约 5–7 次请求取回，耗时 0.64 秒。",
        "左：1,140 バケット、各バケット最大 4 回の HTTP 呼び出しで 139 秒。右：97 個のカレンダーセグメントを 5〜7 回のリクエストで取得し 0.64 秒。",
        "왼쪽: 1,140개 버킷, 버킷당 최대 4회 HTTP 호출로 139초. 오른쪽: 97개 달력 세그먼트를 약 5~7회 요청으로 가져와 0.64초.",
        "Izquierda: 1.140 buckets, cada uno con hasta cuatro llamadas HTTP, en 139 segundos. "
        "Derecha: 97 segmentos de calendario obtenidos en unas cinco a siete peticiones, en 0,64 segundos.",
        "À gauche : 1 140 compartiments, chacun avec jusqu'à quatre appels HTTP, en 139 secondes. "
        "À droite : 97 segments calendaires récupérés en cinq à sept requêtes environ, en 0,64 seconde.",
        "Links: 1.140 Buckets mit je bis zu vier HTTP-Aufrufen, 139 Sekunden. "
        "Rechts: 97 Kalendersegmente in etwa fünf bis sieben Anfragen, 0,64 Sekunden.",
        "Esquerda: 1.140 buckets, cada um com até quatro chamadas HTTP, em 139 segundos. "
        "Direita: 97 segmentos de calendário obtidos em cerca de cinco a sete requisições, em 0,64 segundo.",
        "Слева: 1 140 бакетов, каждому нужно до четырёх HTTP-вызовов, 139 секунд. "
        "Справа: 97 календарных сегментов, около пяти-семи запросов, 0,64 секунды.",
        "يسار: 1,140 دلوًا، كل منها يحتاج حتى أربع مكالمات HTTP، في 139 ثانية. "
        "يمين: 97 مقطعًا تقويميًا تُجلب في نحو خمس إلى سبع طلبات، في 0.64 ثانية.",
        "बाएँ: 1,140 बकेट, हर एक में चार HTTP कॉल तक, 139 सेकंड। "
        "दाएँ: 97 कैलेंडर सेगमेंट, लगभग पाँच से सात रिक्वेस्ट में, 0.64 सेकंड।",
    ),
    "Same output. Two very different request counts.": _t(
        "同样的输出，完全不同的请求数。",
        "同じ出力、まったく違うリクエスト数。",
        "같은 출력, 전혀 다른 요청 수.",
        "La misma salida. Dos números de peticiones muy distintos.",
        "Même sortie. Deux nombres de requêtes très différents.",
        "Gleiche Ausgabe. Zwei sehr unterschiedliche Anzahlen von Anfragen.",
        "A mesma saída. Dois números de requisições muito diferentes.",
        "Тот же результат. Совершенно разное число запросов.",
        "الناتج نفسه. عددان مختلفان جدًا من الطلبات.",
        "वही आउटपुट। रिक्वेस्ट की संख्या बिल्कुल अलग।",
    ),
    "A calendar-level query plan replaces one round trip per bucket with one fetch per level.": _t(
        "日历级查询计划把「每桶一次往返」换成「每层一次取数」。",
        "カレンダー単位のクエリ計画は「バケットごとに 1 往復」を「階層ごとに 1 回の取得」に置き換えます。",
        "달력 단위 쿼리 계획은 '버킷마다 한 번의 왕복'을 '계층마다 한 번의 조회'로 바꿉니다.",
        "Un plan de consulta a nivel de calendario sustituye un viaje de ida y vuelta por bucket "
        "por una sola obtención por nivel.",
        "Un plan de requête au niveau calendaire remplace un aller-retour par compartiment "
        "par une seule récupération par niveau.",
        "Ein Abfrageplan auf Kalenderebene ersetzt einen Roundtrip pro Bucket durch einen Abruf pro Ebene.",
        "Um plano de consulta em nível de calendário troca uma ida e volta por bucket "
        "por uma única busca por nível.",
        "План запроса на уровне календаря заменяет один обмен на бакет одним извлечением на уровень.",
        "خطة استعلام على مستوى التقويم تستبدل رحلة ذهاب وعودة لكل دلو بجلب واحد لكل مستوى.",
        "कैलेंडर-स्तर की क्वेरी योजना \"हर बकेट के लिए एक राउंड ट्रिप\" को "
        "\"हर स्तर के लिए एक फ़ेच\" से बदल देती है।",
    ),
    "Per-bucket client": _t(
        "逐桶客户端",
        "バケット単位クライアント",
        "버킷별 클라이언트",
        "Cliente por bucket",
        "Client par compartiment",
        "Client pro Bucket",
        "Cliente por bucket",
        "Клиент с запросом на бакет",
        "عميل لكل دلو",
        "प्रति-बकेट क्लाइंट",
    ),
    "1,140 buckets": _t(
        "1,140 个桶",
        "1,140 バケット",
        "1,140개 버킷",
        "1.140 buckets",
        "1 140 compartiments",
        "1.140 Buckets",
        "1.140 buckets",
        "1 140 бакетов",
        "1,140 دلوًا",
        "1,140 बकेट",
    ),
    "one aggregation + boundary points per bucket": _t(
        "每桶一次聚合 + 边界点",
        "バケットごとに集約 1 回 + 境界点",
        "버킷마다 집계 1회 + 경계점",
        "una agregación + puntos de borde por bucket",
        "une agrégation + points de bord par compartiment",
        "eine Aggregation + Randpunkte pro Bucket",
        "uma agregação + pontos de borda por bucket",
        "одна агрегация + граничные точки на бакет",
        "تجميع واحد + نقاط الحدود لكل دلو",
        "प्रति बकेट एक एग्रीगेशन + सीमा बिंदु",
    ),
    "up to 4 calls / bucket": _t(
        "每桶最多 4 次调用",
        "バケットあたり最大 4 回の呼び出し",
        "버킷당 최대 4회 호출",
        "hasta 4 llamadas / bucket",
        "jusqu'à 4 appels / compartiment",
        "bis zu 4 Aufrufe / Bucket",
        "até 4 chamadas / bucket",
        "до 4 вызовов / бакет",
        "حتى 4 مكالمات / دلو",
        "प्रति बकेट 4 कॉल तक",
    ),
    "≈4,560 round trips": _t(
        "约 4,560 次往返",
        "約 4,560 往復",
        "약 4,560회 왕복",
        "≈4.560 viajes de ida y vuelta",
        "≈4 560 allers-retours",
        "≈4.560 Roundtrips",
        "≈4.560 idas e voltas",
        "≈4 560 обменов",
        "≈4,560 رحلة ذهاب وعودة",
        "≈4,560 राउंड ट्रिप",
    ),
    "139 s": _t("139 秒", "139 秒", "139초", "139 s", "139 s", "139 s", "139 s", "139 с", "139 ثانية", "139 सेकंड"),
    "0.64 s": _t("0.64 秒", "0.64 秒", "0.64초", "0,64 s", "0,64 s", "0,64 s", "0,64 s", "0,64 с", "0.64 ثانية", "0.64 सेकंड"),
    "Calendar ladder": _t(
        "日历阶梯",
        "カレンダーラダー",
        "달력 사다리",
        "Escalera de calendario",
        "Échelle calendaire",
        "Kalenderleiter",
        "Escada de calendário",
        "Календарная лестница",
        "سلّم التقويم",
        "कैलेंडर लैडर",
    ),
    "month": _t("月", "月", "월", "mes", "mois", "Monat", "mês", "месяц", "شهر", "महीना"),
    "day": _t("日", "日", "일", "día", "jour", "Tag", "dia", "день", "يوم", "दिन"),
    "hour": _t("时", "時", "시", "hora", "heure", "Stunde", "hora", "час", "ساعة", "घंटा"),
    "minute": _t("分", "分", "분", "minuto", "minute", "Minute", "minuto", "минута", "دقيقة", "मिनट"),
    "tail": _t("零头", "テール", "꼬리", "cola", "queue", "Tail", "cauda", "хвост", "ذيل", "टेल"),
    "one fetch per level": _t(
        "每层只取一次",
        "階層ごとに 1 回の取得",
        "계층마다 한 번 조회",
        "una obtención por nivel",
        "une récupération par niveau",
        "ein Abruf pro Ebene",
        "uma busca por nível",
        "одно извлечение на уровень",
        "جلب واحد لكل مستوى",
        "हर स्तर पर एक फ़ेच",
    ),
    "~5–7 requests": _t(
        "约 5–7 次请求",
        "約 5〜7 リクエスト",
        "약 5~7회 요청",
        "~5–7 peticiones",
        "~5–7 requêtes",
        "~5–7 Anfragen",
        "~5–7 requisições",
        "~5–7 запросов",
        "~5–7 طلبات",
        "~5–7 रिक्वेस्ट",
    ),
    "97 segments instead of 423,049 minute buckets. Same output, fewer round trips.": _t(
        "97 段，而不是 423,049 个分钟桶。同样的输出，更少的往返。",
        "423,049 個の分バケットではなく 97 セグメント。同じ出力で、往復はもっと少なく。",
        "423,049개 분 버킷 대신 97개 세그먼트. 같은 출력, 더 적은 왕복.",
        "97 segmentos en lugar de 423.049 buckets de minuto. La misma salida, menos viajes.",
        "97 segments au lieu de 423 049 compartiments minute. Même sortie, moins d'allers-retours.",
        "97 Segmente statt 423.049 Minuten-Buckets. Gleiche Ausgabe, weniger Roundtrips.",
        "97 segmentos em vez de 423.049 buckets de minuto. A mesma saída, menos idas e voltas.",
        "97 сегментов вместо 423 049 минутных бакетов. Тот же результат, меньше обменов.",
        "97 مقطعًا بدلاً من 423,049 دلوًا دقيقيًا. الناتج نفسه، رحلات أقل.",
        "423,049 मिनट-बकेट के बजाय 97 सेगमेंट। वही आउटपुट, कम राउंड ट्रिप।",
    ),
    # ------------------------------------------------------- decomposition
    "Calendar decomposition of a ten-month range": _t(
        "十个月区间的日历分解",
        "10 か月区間のカレンダー分解",
        "10개월 구간의 달력 분해",
        "Descomposición de calendario de un rango de diez meses",
        "Décomposition calendaire d'une plage de dix mois",
        "Kalenderzerlegung eines Zehnmonatsbereichs",
        "Decomposição de calendário de um intervalo de dez meses",
        "Календарная декомпозиция десятимесячного диапазона",
        "تفكيك تقويمي لنطاق عشرة أشهر",
        "दस महीने की रेंज का कैलेंडर विघटन",
    ),
    "The range is split into nine complete months, then the partial October into twenty days, "
    "then October 21 into eighteen hours, then the partial hour into forty-nine minutes and a "
    "one-minute tail: ninety-seven segments in total.": _t(
        "区间先切成 9 个完整月，再把不完整的 10 月切成 20 天，把 10 月 21 日切成 18 个小时，"
        "把不完整的小时切成 49 分钟和 1 个零头：一共 97 段。",
        "区間を 9 個の完全な月に分け、端数の 10 月を 20 日に、10 月 21 日を 18 時間に、"
        "端数の 1 時間を 49 分と 1 分のテールに分けます。合計 97 セグメント。",
        "구간을 9개의 완전한 월로 나누고, 남은 10월을 20일로, 10월 21일을 18시간으로, "
        "남은 1시간을 49분과 1분 꼬리로 나눕니다. 총 97개 세그먼트.",
        "El rango se divide en nueve meses completos, luego el octubre parcial en veinte días, "
        "luego el 21 de octubre en dieciocho horas, luego la hora parcial en cuarenta y nueve minutos "
        "y una cola de un minuto: noventa y siete segmentos en total.",
        "La plage est découpée en neuf mois complets, puis l'octobre partiel en vingt jours, "
        "puis le 21 octobre en dix-huit heures, puis l'heure partielle en quarante-neuf minutes "
        "et une queue d'une minute : quatre-vingt-dix-sept segments au total.",
        "Der Bereich wird in neun vollständige Monate zerlegt, dann der partielle Oktober in "
        "zwanzig Tage, dann der 21. Oktober in achtzehn Stunden, dann die partielle Stunde in "
        "neunundvierzig Minuten und einen Tail von einer Minute: insgesamt siebenundneunzig Segmente.",
        "O intervalo é dividido em nove meses completos, depois o outubro parcial em vinte dias, "
        "depois o dia 21 de outubro em dezoito horas, depois a hora parcial em quarenta e nove minutos "
        "e uma cauda de um minuto: noventa e sete segmentos no total.",
        "Диапазон делится на девять полных месяцев, затем частичный октябрь на двадцать дней, "
        "затем 21 октября на восемнадцать часов, затем частичный час на сорок девять минут "
        "и хвост в одну минуту: всего девяносто семь сегментов.",
        "يُقسَّم النطاق إلى تسعة أشهر كاملة، ثم أكتوبر الجزئي إلى عشرين يومًا، ثم 21 أكتوبر "
        "إلى ثماني عشرة ساعة، ثم الساعة الجزئية إلى تسع وأربعين دقيقة وذيل من دقيقة واحدة: "
        "سبعة وتسعون مقطعًا إجمالاً.",
        "रेंज को नौ पूर्ण महीनों में बाँटा जाता है, फिर आंशिक अक्टूबर को बीस दिनों में, "
        "फिर 21 अक्टूबर को अठारह घंटों में, फिर आंशिक घंटे को उनचास मिनट और एक मिनट के टेल में: "
        "कुल सत्तानवे सेगमेंट।",
    ),
    "One range, four levels, 97 segments": _t(
        "一个区间，四层，97 段",
        "1 区間、4 階層、97 セグメント",
        "하나의 구간, 네 계층, 97개 세그먼트",
        "Un rango, cuatro niveles, 97 segmentos",
        "Une plage, quatre niveaux, 97 segments",
        "Ein Bereich, vier Ebenen, 97 Segmente",
        "Um intervalo, quatro níveis, 97 segmentos",
        "Один диапазон, четыре уровня, 97 сегментов",
        "نطاق واحد، أربعة مستويات، 97 مقطعًا",
        "एक रेंज, चार स्तर, 97 सेगमेंट",
    ),
    "Peel complete units; push the partial left and right edges to the next finer level.": _t(
        "逐层剥离完整单位，把左右残边下沉到下一层。",
        "完全な単位を剥がし、左右の端数は次の細かい階層へ送ります。",
        "완전한 단위를 벗겨 내고, 남은 좌우 끝은 다음 세밀한 계층으로 넘깁니다.",
        "Retira las unidades completas; empuja los bordes parciales izquierdo y derecho "
        "al siguiente nivel más fino.",
        "Retirez les unités complètes ; poussez les bords partiels gauche et droit "
        "au niveau plus fin suivant.",
        "Vollständige Einheiten abziehen; partielle linke und rechte Ränder eine Ebene tiefer schieben.",
        "Retire as unidades completas; empurre as bordas parciais esquerda e direita "
        "para o próximo nível mais fino.",
        "Снимайте полные единицы; частичные левый и правый края отправляйте на следующий, "
        "более мелкий уровень.",
        "انزع الوحدات الكاملة؛ وادفع الحدّين الجزئيين الأيسر والأيمن إلى المستوى الأدق التالي.",
        "पूर्ण इकाइयाँ हटाइए; आंशिक बाएँ और दाएँ किनारे अगले महीन स्तर पर भेजिए।",
    ),
    "full range": _t(
        "完整区间",
        "全区間",
        "전체 구간",
        "rango completo",
        "plage complète",
        "Gesamtbereich",
        "intervalo completo",
        "весь диапазон",
        "النطاق الكامل",
        "पूरी रेंज",
    ),
    "9 complete months": _t(
        "9 个完整月",
        "完全な月 9 個",
        "완전한 월 9개",
        "9 meses completos",
        "9 mois complets",
        "9 vollständige Monate",
        "9 meses completos",
        "9 полных месяцев",
        "9 أشهر كاملة",
        "9 पूर्ण महीने",
    ),
    "October": _t(
        "10 月",
        "10 月",
        "10월",
        "octubre",
        "octobre",
        "Oktober",
        "outubro",
        "октябрь",
        "أكتوبر",
        "अक्टूबर",
    ),
    "20 complete days": _t(
        "20 个完整日",
        "完全な日 20 個",
        "완전한 일 20개",
        "20 días completos",
        "20 jours complets",
        "20 vollständige Tage",
        "20 dias completos",
        "20 полных дней",
        "20 يومًا كاملة",
        "20 पूर्ण दिन",
    ),
    "Oct 21": _t(
        "10 月 21 日",
        "10 月 21 日",
        "10월 21일",
        "21 oct",
        "21 oct.",
        "21. Okt.",
        "21 out",
        "21 окт.",
        "21 أكتوبر",
        "21 अक्टूबर",
    ),
    "18 complete hours": _t(
        "18 个完整小时",
        "完全な時間 18 個",
        "완전한 시간 18개",
        "18 horas completas",
        "18 heures complètes",
        "18 vollständige Stunden",
        "18 horas completas",
        "18 полных часов",
        "18 ساعة كاملة",
        "18 पूर्ण घंटे",
    ),
    "49 complete minutes + 1 tail": _t(
        "49 个完整分钟 + 1 个零头",
        "完全な分 49 個 + テール 1 個",
        "완전한 분 49개 + 꼬리 1개",
        "49 minutos completos + 1 cola",
        "49 minutes complètes + 1 queue",
        "49 vollständige Minuten + 1 Tail",
        "49 minutos completos + 1 cauda",
        "49 полных минут + 1 хвост",
        "49 دقيقة كاملة + ذيل واحد",
        "49 पूर्ण मिनट + 1 टेल",
    ),
    "partial unit": _t(
        "不完整单位",
        "端数の単位",
        "불완전 단위",
        "unidad parcial",
        "unité partielle",
        "partielle Einheit",
        "unidade parcial",
        "частичная единица",
        "وحدة جزئية",
        "आंशिक इकाई",
    ),
    "97 segments  ·  ~5–7 requests  ·  423,049 minute buckets avoided": _t(
        "97 段  ·  约 5–7 次请求  ·  省去 423,049 个分钟桶",
        "97 セグメント  ·  約 5〜7 リクエスト  ·  423,049 個の分バケットを回避",
        "97개 세그먼트  ·  약 5~7회 요청  ·  423,049개 분 버킷 절약",
        "97 segmentos  ·  ~5–7 peticiones  ·  423.049 buckets de minuto evitados",
        "97 segments  ·  ~5–7 requêtes  ·  423 049 compartiments minute évités",
        "97 Segmente  ·  ~5–7 Anfragen  ·  423.049 Minuten-Buckets vermieden",
        "97 segmentos  ·  ~5–7 requisições  ·  423.049 buckets de minuto evitados",
        "97 сегментов  ·  ~5–7 запросов  ·  423 049 минутных бакетов не запрошено",
        "97 مقطعًا  ·  ~5–7 طلبات  ·  تجنّب 423,049 دلوًا دقيقيًا",
        "97 सेगमेंट  ·  ~5–7 रिक्वेस्ट  ·  423,049 मिनट-बकेट बचे",
    ),
    "The same decomposition works for any range and any configured finest level.": _t(
        "同一套分解适用于任意区间和任意配置的最细层级。",
        "同じ分解は、任意の区間と任意の最細階層でそのまま使えます。",
        "같은 분해가 어떤 구간과 어떤 최세밀 계층에도 그대로 적용됩니다.",
        "La misma descomposición funciona para cualquier rango y cualquier nivel más fino configurado.",
        "La même décomposition vaut pour toute plage et tout niveau le plus fin configuré.",
        "Dieselbe Zerlegung funktioniert für jeden Bereich und jede konfigurierte feinste Ebene.",
        "A mesma decomposição vale para qualquer intervalo e qualquer nível mais fino configurado.",
        "Та же декомпозиция работает для любого диапазона и любого настроенного самого мелкого уровня.",
        "التفكيك نفسه يعمل مع أي نطاق وأي مستوى أدق مُهيّأ.",
        "वही विघटन किसी भी रेंज और किसी भी कॉन्फ़िगर किए गए सबसे महीन स्तर पर काम करता है।",
    ),
    # --------------------------------------------------------- architecture
    "One query plan, two read paths": _t(
        "一份查询计划，两条读取路径",
        "1 つのクエリ計画、2 つの読み取り経路",
        "하나의 쿼리 계획, 두 개의 읽기 경로",
        "Un plan de consulta, dos rutas de lectura",
        "Un plan de requête, deux chemins de lecture",
        "Ein Abfrageplan, zwei Lesepfade",
        "Um plano de consulta, dois caminhos de leitura",
        "Один план запроса, два пути чтения",
        "خطة استعلام واحدة، مسارا قراءة",
        "एक क्वेरी योजना, दो पढ़ने के रास्ते",
    ),
    "Top: decompose, group runs by fetch level and contiguity, fetch each run once within the "
    "bucket limit, and fold locally. Bottom: split each segment against coverage, sum covered "
    "parts locally, fetch uncovered parts from the source, and merge the two.": _t(
        "上：分解，按取数层级和连续性对 run 分组，每个 run 在桶数上限内取一次，本地折叠。"
        "下：按覆盖切分每个段，已覆盖部分本地求和，未覆盖部分取源，再合并两者。",
        "上：分解し、取得階層と連続性で run をまとめ、各 run をバケット上限内で 1 回取得し、"
        "ローカルで折り畳みます。下：各セグメントをカバレッジで分割し、カバー済み部分を"
        "ローカルで合計、未カバー部分をソースから取得し、両者を統合します。",
        "위: 분해하고, 조회 계층과 연속성으로 run을 묶고, 각 run을 버킷 한도 안에서 한 번 "
        "조회한 뒤 로컬에서 접습니다. 아래: 각 세그먼트를 커버리지로 나누고, 커버된 부분은 "
        "로컬에서 합산하고, 커버되지 않은 부분은 소스에서 가져와 둘을 합칩니다.",
        "Arriba: descompone, agrupa los run por nivel de obtención y contigüidad, obtén cada run "
        "una vez dentro del límite de buckets y pliega localmente. Abajo: divide cada segmento "
        "según la cobertura, suma localmente las partes cubiertas, obtén las no cubiertas del "
        "origen y combina ambas.",
        "Haut : décomposer, regrouper les run par niveau de récupération et contiguïté, récupérer "
        "chaque run une fois dans la limite de compartiments, puis replier localement. Bas : "
        "découper chaque segment selon la couverture, sommer localement les parties couvertes, "
        "récupérer les parties non couvertes depuis la source, puis fusionner les deux.",
        "Oben: zerlegen, Runs nach Abrufebene und Zusammenhängendkeit gruppieren, jeden Run einmal "
        "innerhalb des Bucket-Limits abrufen und lokal falten. Unten: jedes Segment an der "
        "Abdeckung teilen, abgedeckte Teile lokal summieren, nicht abgedeckte Teile von der "
        "Quelle holen und beide zusammenführen.",
        "Acima: decomponha, agrupe os run por nível de busca e contiguidade, busque cada run uma "
        "vez dentro do limite de buckets e dobre localmente. Abaixo: divida cada segmento pela "
        "cobertura, some localmente as partes cobertas, busque as não cobertas na origem e "
        "combine as duas.",
        "Сверху: разложить, сгруппировать run по уровню извлечения и смежности, извлечь каждый "
        "run один раз в пределах лимита бакетов и свернуть локально. Снизу: разрезать каждый "
        "сегмент по покрытию, суммировать покрытые части локально, запросить непокрытые из "
        "источника и объединить оба результата.",
        "أعلى: فكّك، وجمّع الـ run حسب مستوى الجلب والتلاصق، واجلب كل run مرة واحدة ضمن حد "
        "الدلاء، ثم اطوِ محليًا. أسفل: قسّم كل مقطع حسب التغطية، واجمع الأجزاء المغطاة "
        "محليًا، واجلب غير المغطاة من المصدر، ثم ادمج الاثنين.",
        "ऊपर: विघटित करें, run को फ़ेच स्तर और निरंतरता से समूहित करें, हर run को बकेट सीमा "
        "के भीतर एक बार फ़ेच करें, और स्थानीय रूप से मोड़ें। नीचे: हर सेगमेंट को कवरेज पर "
        "विभाजित करें, कवर किए भाग स्थानीय रूप से जोड़ें, बाकी स्रोत से लाएँ, और दोनों मिलाएँ।",
    ),
    "The source path plans requests. The local-first path also reuses materialized coverage.": _t(
        "纯源路径负责规划请求；本地优先路径还会复用已固化的覆盖。",
        "ソース経路はリクエストを計画します。ローカル優先経路はマテリアライズ済みのカバレッジも再利用します。",
        "소스 경로는 요청을 계획합니다. 로컬 우선 경로는 구체화된 커버리지까지 재사용합니다.",
        "La ruta solo-origen planifica peticiones. La ruta local-primero reutiliza además "
        "la cobertura materializada.",
        "Le chemin source planifie les requêtes. Le chemin local-d'abord réutilise aussi "
        "la couverture matérialisée.",
        "Der Quellpfad plant Anfragen. Der Local-First-Pfad nutzt zusätzlich materialisierte Abdeckung.",
        "O caminho somente-origem planeja requisições. O caminho local-primeiro também reutiliza "
        "a cobertura materializada.",
        "Путь только-источник планирует запросы. Путь local-first дополнительно переиспользует "
        "материализованное покрытие.",
        "مسار المصدر فقط يخطّط الطلبات. مسار المحلي أولًا يعيد استخدام التغطية المجسّدة أيضًا.",
        "स्रोत-केवल रास्ता रिक्वेस्ट की योजना बनाता है। लोकल-फ़र्स्ट रास्ता सामग्रीकृत कवरेज "
        "का भी पुनः उपयोग करता है।",
    ),
    "Source-only read": _t(
        "纯源读取",
        "ソースのみの読み取り",
        "소스 전용 읽기",
        "Lectura solo-origen",
        "Lecture source seule",
        "Nur-Quelle-Lesen",
        "Leitura somente-origem",
        "Чтение только из источника",
        "قراءة من المصدر فقط",
        "स्रोत-केवल पढ़ना",
    ),
    "Calendar decomposition": _t(
        "日历分解",
        "カレンダー分解",
        "달력 분해",
        "Descomposición de calendario",
        "Décomposition calendaire",
        "Kalenderzerlegung",
        "Decomposição de calendário",
        "Календарная декомпозиция",
        "تفكيك تقويمي",
        "कैलेंडर विघटन",
    ),
    "complete units only": _t(
        "只输出完整单位",
        "完全な単位のみ",
        "완전한 단위만",
        "solo unidades completas",
        "unités complètes uniquement",
        "nur vollständige Einheiten",
        "somente unidades completas",
        "только полные единицы",
        "الوحدات الكاملة فقط",
        "केवल पूर्ण इकाइयाँ",
    ),
    "partial edges go finer": _t(
        "残边下沉到更细层",
        "端数は細かい階層へ",
        "끝 부분은 더 세밀하게",
        "los bordes parciales bajan",
        "les bords partiels descendent",
        "partielle Ränder tiefer",
        "bordas parciais descem",
        "частичные края — ниже",
        "الأطراف الجزئية تنزل",
        "आंशिक किनारे नीचे",
    ),
    "Group runs": _t(
        "对 run 分组",
        "run をまとめる",
        "run 묶기",
        "Agrupar run",
        "Regrouper les run",
        "Runs gruppieren",
        "Agrupar run",
        "Группировать run",
        "تجميع الـ run",
        "run समूहित करें",
    ),
    "fetch level + contiguity": _t(
        "取数层级 + 连续性",
        "取得階層 + 連続性",
        "조회 계층 + 연속성",
        "nivel de obtención + contigüidad",
        "niveau de récupération + contiguïté",
        "Abrufebene + Zusammenhängendkeit",
        "nível de busca + contiguidade",
        "уровень извлечения + смежность",
        "مستوى الجلب + التلاصق",
        "फ़ेच स्तर + निरंतरता",
    ),
    "never adjacency alone": _t(
        "仅相邻不算",
        "隣接だけでは不十分",
        "인접만으로는 안 됨",
        "nunca solo adyacencia",
        "jamais l'adjacence seule",
        "nie Nachbarschaft allein",
        "nunca só adjacência",
        "не только соседство",
        "ليس التجاور وحده",
        "सिर्फ़ सटना नहीं",
    ),
    "Fetch once per run": _t(
        "每个 run 取一次",
        "run ごとに 1 回取得",
        "run마다 한 번 조회",
        "Obtener una vez por run",
        "Récupérer une fois par run",
        "Einmal pro Run abrufen",
        "Buscar uma vez por run",
        "Извлечь один раз на run",
        "جلب واحد لكل run",
        "प्रति run एक बार फ़ेच",
    ),
    "≤ K buckets per request": _t(
        "每请求 ≤ K 个桶",
        "リクエストあたり ≤ K バケット",
        "요청당 ≤ K 버킷",
        "≤ K buckets por petición",
        "≤ K compartiments par requête",
        "≤ K Buckets pro Anfrage",
        "≤ K buckets por requisição",
        "≤ K бакетов на запрос",
        "≤ K دلوًا لكل طلب",
        "प्रति रिक्वेस्ट ≤ K बकेट",
    ),
    "next finer aggregation": _t(
        "下一级更细聚合",
        "次の細かい集約",
        "다음 세밀한 집계",
        "siguiente agregación más fina",
        "agrégation plus fine suivante",
        "nächste feinere Aggregation",
        "próxima agregação mais fina",
        "следующая более мелкая агрегация",
        "التجميع الأدق التالي",
        "अगला महीन एग्रीगेशन",
    ),
    "Fold locally": _t(
        "本地折叠",
        "ローカルで折り畳む",
        "로컬에서 접기",
        "Plegar localmente",
        "Replier localement",
        "Lokal falten",
        "Dobrar localmente",
        "Свернуть локально",
        "الطي محليًا",
        "स्थानीय रूप से मोड़ें",
    ),
    "sum buckets into": _t(
        "把桶求和为",
        "バケットを合計して",
        "버킷을 합산해",
        "sumar buckets en",
        "sommer les compartiments en",
        "Buckets summieren zu",
        "somar buckets em",
        "суммировать бакеты в",
        "جمع الدلاء في",
        "बकेट जोड़कर बनाएँ",
    ),
    "output segments": _t(
        "输出段",
        "出力セグメントへ",
        "출력 세그먼트로",
        "segmentos de salida",
        "segments de sortie",
        "Ausgabesegmenten",
        "segmentos de saída",
        "выходные сегменты",
        "مقاطع الإخراج",
        "आउटपुट सेगमेंट",
    ),
    "months → day buckets": _t(
        "月 → 日桶",
        "月 → 日バケット",
        "월 → 일 버킷",
        "meses → buckets de día",
        "mois → compartiments jour",
        "Monate → Tages-Buckets",
        "meses → buckets de dia",
        "месяцы → дневные бакеты",
        "أشهر → دلاء يوم",
        "महीने → दिन बकेट",
    ),
    "days → hour buckets": _t(
        "日 → 小时桶",
        "日 → 時バケット",
        "일 → 시 버킷",
        "días → buckets de hora",
        "jours → compartiments heure",
        "Tage → Stunden-Buckets",
        "dias → buckets de hora",
        "дни → часовые бакеты",
        "أيام → دلاء ساعة",
        "दिन → घंटा बकेट",
    ),
    "hours + minutes → minute": _t(
        "小时 + 分钟 → 分钟",
        "時 + 分 → 分",
        "시 + 분 → 분",
        "horas + minutos → minuto",
        "heures + minutes → minute",
        "Stunden + Minuten → Minute",
        "horas + minutos → minuto",
        "часы + минуты → минута",
        "ساعات + دقائق → دقيقة",
        "घंटे + मिनट → मिनट",
    ),
    "97 segments · ~5–7 requests": _t(
        "97 段 · 约 5–7 次请求",
        "97 セグメント · 約 5〜7 リクエスト",
        "97개 세그먼트 · 약 5~7회 요청",
        "97 segmentos · ~5–7 peticiones",
        "97 segments · ~5–7 requêtes",
        "97 Segmente · ~5–7 Anfragen",
        "97 segmentos · ~5–7 requisições",
        "97 сегментов · ~5–7 запросов",
        "97 مقطعًا · ~5–7 طلبات",
        "97 सेगमेंट · ~5–7 रिक्वेस्ट",
    ),
    "Local-first read": _t(
        "本地优先读取",
        "ローカル優先の読み取り",
        "로컬 우선 읽기",
        "Lectura local-primero",
        "Lecture local-d'abord",
        "Local-First-Lesen",
        "Leitura local-primeiro",
        "Чтение local-first",
        "قراءة المحلي أولًا",
        "लोकल-फ़र्स्ट पढ़ना",
    ),
    "Segment": _t("段", "セグメント", "세그먼트", "Segmento", "Segment", "Segment", "Segmento", "Сегмент", "مقطع", "सेगमेंट"),
    "Split against": _t(
        "按覆盖",
        "カバレッジで",
        "커버리지로",
        "Dividir según",
        "Découper selon",
        "Teilen an der",
        "Dividir pela",
        "Разрезать по",
        "التقسيم حسب",
        "कवरेज पर",
    ),
    "coverage": _t(
        "切分",
        "分割",
        "분할",
        "cobertura",
        "la couverture",
        "Abdeckung",
        "cobertura",
        "покрытию",
        "التغطية",
        "विभाजित",
    ),
    "Covered": _t(
        "已覆盖",
        "カバー済み",
        "커버됨",
        "Cubierto",
        "Couvert",
        "Abgedeckt",
        "Coberto",
        "Покрыто",
        "مغطى",
        "कवर किया",
    ),
    "one batched local SQL sum": _t(
        "一条批量本地 SQL 求和",
        "バッチ化したローカル SQL 合計 1 回",
        "배치 처리된 로컬 SQL 합계 1회",
        "una suma SQL local por lote",
        "une somme SQL locale par lot",
        "eine gebündelte lokale SQL-Summe",
        "uma soma SQL local em lote",
        "одна пакетная локальная SQL-сумма",
        "مجموع SQL محلي واحد على دفعات",
        "एक बैच स्थानीय SQL योग",
    ),
    "Uncovered": _t(
        "未覆盖",
        "未カバー",
        "커버 안 됨",
        "No cubierto",
        "Non couvert",
        "Nicht abgedeckt",
        "Não coberto",
        "Не покрыто",
        "غير مغطى",
        "कवर नहीं",
    ),
    "source fetch, grouped or partial": _t(
        "取源，分组或部分",
        "ソース取得（まとめて／一部）",
        "소스 조회(묶음 또는 부분)",
        "obtención del origen, agrupada o parcial",
        "récupération source, groupée ou partielle",
        "Quellabruf, gruppiert oder partiell",
        "busca na origem, agrupada ou parcial",
        "запрос к источнику, группой или частично",
        "جلب من المصدر، مجمّعًا أو جزئيًا",
        "स्रोत फ़ेच, समूहित या आंशिक",
    ),
    "Merge": _t("合并", "統合", "병합", "Combinar", "Fusionner", "Zusammenführen", "Combinar", "Объединить", "الدمج", "मिलाएँ"),
    "local + source": _t(
        "本地 + 源",
        "ローカル + ソース",
        "로컬 + 소스",
        "local + origen",
        "local + source",
        "lokal + Quelle",
        "local + origem",
        "локально + источник",
        "محلي + مصدر",
        "स्थानीय + स्रोत",
    ),
    "Value": _t("取值", "値", "값", "Valor", "Valeur", "Wert", "Valor", "Значение", "القيمة", "मान"),
    "coverage for the segment": _t(
        "该段的覆盖情况",
        "セグメントのカバレッジ",
        "해당 세그먼트의 커버리지",
        "cobertura del segmento",
        "couverture du segment",
        "Abdeckung für das Segment",
        "cobertura do segmento",
        "покрытие сегмента",
        "تغطية المقطع",
        "सेगमेंट का कवरेज",
    ),
    "covered": _t(
        "已覆盖",
        "カバー済み",
        "커버됨",
        "cubierto",
        "couvert",
        "abgedeckt",
        "coberto",
        "покрыто",
        "مغطى",
        "कवर किया",
    ),
    "uncovered": _t(
        "未覆盖",
        "未カバー",
        "커버 안 됨",
        "no cubierto",
        "non couvert",
        "nicht abgedeckt",
        "não coberto",
        "не покрыто",
        "غير مغطى",
        "कवर नहीं",
    ),
    "Coverage is recorded only up to now − 5 minutes; a failed pull invalidates it before the "
    "next read.": _t(
        "覆盖只记录到 now − 5 分钟；拉取失败会在下次读取前使其失效。",
        "カバレッジは now − 5 分までしか記録されません。取得に失敗すると次の読み取り前に無効化されます。",
        "커버리지는 now − 5분까지만 기록됩니다. 가져오기에 실패하면 다음 읽기 전에 무효화됩니다.",
        "La cobertura solo se registra hasta now − 5 minutos; una obtención fallida la invalida "
        "antes de la siguiente lectura.",
        "La couverture n'est enregistrée que jusqu'à now − 5 minutes ; une récupération échouée "
        "l'invalide avant la lecture suivante.",
        "Abdeckung wird nur bis now − 5 Minuten erfasst; ein fehlgeschlagener Abruf macht sie "
        "vor dem nächsten Lesen ungültig.",
        "A cobertura só é registrada até now − 5 minutos; uma busca falha a invalida antes da "
        "próxima leitura.",
        "Покрытие фиксируется только до now − 5 минут; неудачное извлечение аннулирует его до "
        "следующего чтения.",
        "تُسجَّل التغطية حتى now − 5 دقائق فقط؛ وفشل الجلب يبطلها قبل القراءة التالية.",
        "कवरेज केवल now − 5 मिनट तक दर्ज होता है; असफल फ़ेच अगली पढ़ाई से पहले उसे अमान्य कर देता है।",
    ),
    "A range is marked covered even when the source returned zero points: “we asked, there is "
    "nothing”.": _t(
        "即使源端返回零个点，区间也会被标记为已覆盖：「问过了，确实没有」。",
        "ソースが 0 点を返しても、その区間はカバー済みとして記録されます（「問い合わせたが、何もなかった」）。",
        "소스가 0개 점을 반환해도 구간은 커버된 것으로 기록됩니다. \"물어봤지만 아무것도 없다\"는 사실이기 때문입니다.",
        "Un rango se marca como cubierto aunque el origen devuelva cero puntos: «preguntamos y no hay nada».",
        "Une plage est marquée couverte même si la source a renvoyé zéro point : « on a demandé, il n'y a rien ».",
        "Ein Bereich gilt auch dann als abgedeckt, wenn die Quelle null Punkte liefert: "
        "„gefragt, es gibt nichts“.",
        "Um intervalo é marcado como coberto mesmo quando a origem devolve zero pontos: "
        "“perguntamos, não há nada”.",
        "Диапазон помечается покрытым, даже если источник вернул ноль точек: «спросили — там ничего нет».",
        "يُعلَّم النطاق كمغطى حتى لو أعاد المصدر صفر نقاط: «سألنا، ولا يوجد شيء».",
        "स्रोत शून्य बिंदु लौटाए तब भी रेंज कवर के रूप में चिह्नित होती है: \"पूछा, वहाँ कुछ नहीं है\"।",
    ),
    "The same segment model drives sum, verify and repair.": _t(
        "同一套段模型驱动 sum、verify 和 repair。",
        "同じセグメントモデルが sum・verify・repair を駆動します。",
        "같은 세그먼트 모델이 sum, verify, repair를 구동합니다.",
        "El mismo modelo de segmentos impulsa sum, verify y repair.",
        "Le même modèle de segments pilote sum, verify et repair.",
        "Dasselbe Segmentmodell treibt sum, verify und repair.",
        "O mesmo modelo de segmentos move sum, verify e repair.",
        "Та же модель сегментов управляет sum, verify и repair.",
        "نموذج المقاطع نفسه يقود sum وverify وrepair.",
        "वही सेगमेंट मॉडल sum, verify और repair को चलाता है।",
    ),
}


# --------------------------------------------------------------------------
# Text measurement
# --------------------------------------------------------------------------
# Labels that stay identical in every language: counts, the API box, the
# half-open interval notation, mode identifiers and a clock label.
PASSTHROUGH = {"API", "9", "20", "18", "49", "1", "18:00", "[start, end)", "local | tb | mixed"}

_NARROW = set("ilj.,'`:;!|()[]{}· ")
_WIDE = set("mwMW@")


def _em_width(ch: str) -> float:
    """Rough advance width in em for one character."""
    cp = ord(ch)
    if 0x4E00 <= cp <= 0x9FFF or 0x3400 <= cp <= 0x4DBF:
        return 1.0
    if 0x3040 <= cp <= 0x30FF or 0x31F0 <= cp <= 0x31FF:  # kana
        return 1.0
    if 0xAC00 <= cp <= 0xD7AF:  # hangul
        return 1.0
    if 0x0600 <= cp <= 0x06FF or 0x0750 <= cp <= 0x077F:  # arabic
        return 0.52
    if 0x0900 <= cp <= 0x097F:  # devanagari
        return 0.55
    if ch in _NARROW:
        return 0.28
    if ch in _WIDE:
        return 0.85
    if ch.isupper():
        return 0.62
    if ch.isdigit():
        return 0.56
    return 0.5


def estimate_width(text: str, size: float) -> float:
    return sum(_em_width(ch) for ch in text) * size


def _fit_font_size(source: str, translated: str, size: float) -> float:
    """Shrink a label only when the translation is much wider than the original."""
    if not source or not translated:
        return size
    allowed = estimate_width(source, size) * 1.12
    actual = estimate_width(translated, size)
    if actual <= allowed:
        return size
    return max(size * 0.7, size * allowed / actual)


# --------------------------------------------------------------------------
# SVG rewriting
# --------------------------------------------------------------------------
def _local_name(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def localize(source: Path, lang: str) -> tuple[ET.ElementTree, list[str]]:
    """Return the localized tree plus the list of strings left untranslated."""
    sans, mono, rtl = LANGS[lang]
    tree = ET.parse(source)
    missing: list[str] = []

    for elem in tree.iter():
        name = _local_name(elem.tag)
        if name not in ("text", "title", "desc"):
            continue
        if elem.text is None:
            continue
        original = elem.text
        if not original.strip():
            continue
        translated = TRANSLATIONS.get(original, {}).get(lang)
        if translated is None:
            if original.strip() in PASSTHROUGH:
                continue
            missing.append(original)
            continue

        elem.text = translated

        if name == "text":
            family = elem.get("font-family", "")
            elem.set("font-family", mono if "monospace" in family else sans)

            size = elem.get("font-size")
            if size:
                elem.set("font-size", f"{_fit_font_size(original, translated, float(size)):.1f}")

            if rtl:
                elem.set("direction", "rtl")
                anchor = elem.get("text-anchor", "start")
                if anchor == "start":
                    elem.set("text-anchor", "end")
                elif anchor == "end":
                    elem.set("text-anchor", "start")

    return tree, missing


def find_chrome() -> str:
    candidates = [
        os.environ.get("CHROME_PATH", ""),
        r"C:\Program Files\Google\Chrome\Application\chrome.exe",
        r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
        r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
        r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
        "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
        "/usr/bin/google-chrome",
        "/usr/bin/chromium",
    ]
    for candidate in candidates:
        if candidate and Path(candidate).exists():
            return candidate
    raise SystemExit("Chrome not found; set CHROME_PATH to a Chrome or Edge executable")


def render(chrome: str, svg: Path, png: Path, width: int, height: int) -> None:
    with tempfile.TemporaryDirectory(prefix="rl-render-") as profile:
        subprocess.run(
            [
                chrome,
                "--headless",
                "--disable-gpu",
                "--hide-scrollbars",
                "--no-first-run",
                "--disable-extensions",
                f"--user-data-dir={profile}",
                "--force-device-scale-factor=2",
                f"--window-size={width},{height}",
                f"--screenshot={png}",
                svg.resolve().as_uri(),
            ],
            check=True,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--lang", action="append", choices=sorted(LANGS), help="limit to one language")
    parser.add_argument("--check", action="store_true", help="report missing translations and exit")
    parser.add_argument("--no-render", action="store_true", help="write SVGs without rendering PNGs")
    args = parser.parse_args()

    languages = args.lang or sorted(LANGS)
    chrome = None if args.no_render or args.check else find_chrome()
    problems = 0

    for lang in languages:
        for image in LANG_IMAGES[lang]:
            source = ASSETS / f"{image}.svg"
            tree, missing = localize(source, lang)
            if missing:
                problems += len(missing)
                for text in missing:
                    print(f"  missing {lang}: {text[:70]!r}", file=sys.stderr)
                continue
            if args.check:
                continue

            target = ASSETS / f"{image}.{lang}.svg"
            tree.write(target, encoding="utf-8", xml_declaration=False)
            if not args.no_render:
                width, height = IMAGES[image]
                render(chrome, target, target.with_suffix(".png"), width, height)
            print(f"  {target.relative_to(ROOT)}")

    if args.check:
        print("translations complete" if not problems else f"{problems} missing strings")
    return 1 if problems else 0


if __name__ == "__main__":
    raise SystemExit(main())
