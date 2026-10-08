# BIST Fundamental Intelligence

BIST hisseleri için tam evrenli temel analiz, sektör/endüstri karşılaştırması ve profesyonel raporlama motoru.

## v0.2 — Full Universe Engine

Bir hisse kodu verildiğinde sistem artık sabit sayıda "emsal" seçmez. Her çalışmada güncel BIST pay evrenini dinamik olarak çeker ve seçilen hisseyi dört ayrı dağılım içinde değerlendirir:

- Aynı **endüstrinin tamamı**
- Aynı **sektörün tamamı**
- Güncel **BIST100 üyelerinin tamamı**
- Veri bulunan **tüm BIST pay evreni**

Karşılaştırmalarda aynı şirketin farklı pay sınıflarının dağılımı yapay biçimde bozmasını azaltmak için şirket bazlı tekilleştirme uygulanır. Eksik finansal veri sıfır kabul edilmez; ilgili metrik örnekleminden çıkarılır ve raporda gerçek \`n=\` sayısı gösterilir.

## Analiz katmanları

Her finansal faktör için raporda aynı anda şunlar gösterilir:

1. Şirketin güncel değeri
2. Profil bazlı mutlak değerlendirme
3. Endüstri medyanı ve yüzdelik/göreli konum
4. Sektör medyanı ve yüzdelik/göreli konum
5. BIST100 medyanı ve yüzdelik/göreli konum
6. Tüm BIST medyanı ve yüzdelik/göreli konum
7. Faktöre özel profesyonel Türkçe yorum

Ana faktör grupları:

- **Büyüme:** ciro, EPS ve net kâr büyümesi
- **Kârlılık:** ROE, ROA, ROIC, brüt/faaliyet/net/FAVÖK marjları
- **Finansal Sağlık:** cari oran, likidite, borç/özsermaye, net borç/FAVÖK, özsermaye/varlık
- **Nakit Kalitesi:** FCF marjı ve Piotroski F-Score
- **Değerleme:** F/K, PD/DD, FD/FAVÖK ve Fiyat/FCF
- **Bilgi:** temettü verimi

Banka ve sigorta gibi finansal şirketlerde sanayi şirketlerine özgü ve anlamsız kalabilecek bazı oranlar otomatik olarak skor dışı bırakılır. GYO/Holding tarafında PD/DD gerçek NAD iskontosu olarak kabul edilmez.

## Profesyonel genel değerlendirme

Raporun sonunda sistem yalnız puan tekrarı yapmaz. Büyüme, kârlılık, finansal sağlık, nakit kalitesi ve değerlemeyi birlikte okuyarak:

- şirketin güçlü/zayıf yönlerini,
- iyi şirket / ucuz hisse ayrımını,
- sektör içindeki konumunu,
- BIST100 ve tüm BIST dağılımındaki yerini,
- BIST100'e karşı 3A / 6A / 12A relatif fiyat performansını

tek bir profesyonel genel değerlendirmede birleştirir.

## Veri

- Temel evren ve finansal karşılaştırmalar: **TradingView Screener** veri alanları
- XU100 fiyat performansı: **Yahoo Finance**
- Çıktılar: HTML + JSON + o çalışmada kullanılan tam BIST evreni CSV snapshot

> Veri kapsamı sağlayıcıya göre değişebilir. Eksik veri uydurulmaz. Mutlak referans bantları "evrensel doğru değer" değildir; finansal oran mantığı ve şirket profiline göre kalibre edilmiş analitik eşiklerdir. Dağılım karşılaştırmaları ayrı gösterilir.

## GitHub üzerinden kullanım

1. **Actions** sekmesine gir.
2. **Hisse Analizi** workflow'unu aç.
3. **Run workflow** seç.
4. \`symbol\` alanına örneğin \`ASELS\`, \`AKBNK\` veya \`TUPRS\` yaz.
5. Çalışma bittiğinde \`bist-report-<SEMBOL>\` artifact'ını indir.

Artifact içinde:

- \`<SEMBOL>_report.html\`
- \`<SEMBOL>_report.json\`
- \`<SEMBOL>_universe_snapshot.csv\`

bulunur.

## Yerel kullanım

\`\`\`powershell
pip install -r requirements.txt
python analyze.py ASELS
\`\`\`

## Sonraki aşamalar

- KAP/resmî finansal tablolarla veri doğrulama katmanı
- 3Y/5Y tarihsel finansal trend ve şirketin kendi tarihsel medyanı
- Banka, GYO, Holding, Sigorta için daha derin özel motorlar
- Sektör sıralama/tarama komutları
- Telegram \`/analiz ASELS\`
- Teknik + temel + relatif güç birleşik araştırma motoru

## Uyarı

Bu proje araştırma ve veri analizi amaçlıdır. Üretilen raporlar yatırım tavsiyesi değildir.
