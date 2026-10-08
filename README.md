# BIST Fundamental Intelligence

BIST hisseleri için tam evrenli temel analiz, sektör/endüstri karşılaştırması ve profesyonel raporlama motoru.

## v0.3 — Full Universe + Historical Financial Intelligence

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

- **BorsaPy**: KAP şirket metadata'sı, gerçek BIST endeks bileşenleri, hedef şirket için İş Yatırım mali tabloları ve BIST'e özgü doğrulama katmanı

- Temel evren ve finansal karşılaştırmalar: **TradingView Screener** veri alanları
- XU100 ve uygun sektör endeksi fiyat performansı: **BorsaPy/TradingView öncelikli**, Yahoo Finance fallback
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


## GYO özel yaklaşımı

GYO'lar sanayi şirketleriyle aynı değerleme motoruna zorlanmaz. Özellikle:

- F/K, PD/DD, FD/FAVÖK, Fiyat/FCF, EPS büyümesi, Net Borç/FAVÖK, FCF marjı ve Piotroski gibi metrikler raporda görülebilir ancak **genel GYO değerleme/kalite skorunu otomatik olarak belirlemez**.
- Seçilen GYO için gerçekleşen F/K, PD/DD ve FD/FAVÖK verisinde **İş Yatırım şirket kartı önceliklidir**. İş Yatırım oranı A/D gösteriyorsa başka sağlayıcıdaki sayı gerçekleşen oranmış gibi skora sokulmaz.
- PD/DD yalnızca defter değeri karşılaştırmasıdır; **NAD (Net Aktif Değer) iskontosu değildir**.
- Profesyonel GYO değerlemesinde gerçek NAD/PD-NAD, portföy ekspertiz değerleri, arsa/proje stoğu, ön satış ve teslimat takvimi, finansman ihtiyacı ile XGMYO relatif performansı birlikte değerlendirilmelidir.
- Proje geliştirici GYO'larda negatif FCF tek başına sanayi şirketlerindeki kadar doğrudan kalite cezası sayılmaz; yatırım/proje geliştirme döngüsü ayrıca ayrıştırılır.
- Net borç hesabında finansal borçlara ek olarak diğer finansal yükümlülükler dikkate alınır; nakit ve finansal yatırımlar düşülür ve sonuç İş Yatırım şirket kartıyla çapraz kontrol edilir.

Regresyon testleri EKGYO üzerinde bu kuralları semantik olarak doğrular; yalnızca script'in hata vermeden çalışması yeterli kabul edilmez.


## Tüm BIST otomatik kalite/audit sistemi

Repo artık yalnız ASELS/AKBNK/EKGYO spot regresyonlarıyla yetinmez. \`Full BIST Audit\` workflow'u güncel BIST şirket evrenini şirket bazında tekilleştirir ve hisseleri 8 paralel shard'a bölerek **her sembolü tek tek** kontrol eder.

Her şirket için denetlenen başlıca kurallar:

- profil sınıflandırması ve profil-bazlı skor dışı metrikler,
- Banka/GYO/Holding/Sigorta/Yatırım Ortaklığı özel kuralları,
- bilanço/gelir tablosu çekilebilirliği ve çekirdek satır kapsaması,
- negatif özkaynakta anlamsız ROE/PD-DD/Borç-Özsermaye skorlarının engellenmesi,
- İş Yatırım ve TradingView oranları arasındaki büyük veri uyuşmazlıkları,
- aşırı/şüpheli finansal oranlar,
- sektör/endüstri/BIST100/tüm BIST karşılaştırma evrenlerinin yeterliliği,
- GYO için XGMYO, banka için XBANK gibi profil-endeks eşleşmeleri,
- skor ve yüzdeliklerin 0–100 matematiksel sınırları.

Workflow sonunda \`full-bist-audit\` artifact'ı üretilir:

- \`full_bist_audit.csv\` — şirket bazında tüm bulgular,
- \`full_bist_audit_summary.json\` — makine okunur özet,
- \`full_bist_audit.md\` — insan okunur hata/uyarı özeti.

Audit'te bir şirketin veri sağlayıcısında eksik veri bulunması tek başına "motor hatası" sayılmaz. Sistem **motor hatası**, **kritik muhasebe/profil hatası**, **kaynak uyuşmazlığı** ve **veri eksikliği/uyarı** ayrımını korur.

## Uyarı

Bu proje araştırma ve veri analizi amaçlıdır. Üretilen raporlar yatırım tavsiyesi değildir.

## BorsaPy entegrasyonu

BorsaPy tüm BIST evreninin ağır bilanço çağrıları için kullanılmaz. Çapraz kesit karşılaştırması TradingView Screener ile hızlı tutulur; BorsaPy seçilen hisse üzerinde derin doğrulama ve tarihsel mali tablo erişimi için kullanılır. Bankalarda UFRS, diğer şirketlerde XI_29 mali tablo formatı tercih edilir.

## Tamamlanan ek katmanlar

- **BorsaPy/KAP/İş Yatırım doğrulaması:** hedef hissenin BIST'e özgü şirket bilgileri ve mali tabloları ikinci veri katmanından kontrol edilir.
- **12 çeyreklik tarihsel analiz:** son 12 çeyrek bilanço/gelir tablosu; sanayi şirketlerinde nakit akış tablosu.
- **5 yıllık yıllık tablo erişimi:** uygun veride 3Y CAGR ve uzun dönem büyüme teyidi.
- **Nakit kalitesi:** CFO/net kâr, FCF marjı, yatırım harcaması/OCF ayrımı ve kârın nakde dönüşümü.
- **Bilanço trendi:** nakit, finansal borç, net borç, özsermaye, aktif ve likidite değişimleri.
- **Banka/UFRS motoru:** net kâr, net faiz geliri, ücret-komisyon geliri, kredi, mevduat, özsermaye ve aktif büyümesi ayrı okunur; sanayi tipi FCF/net borç mantığı bankalara zorla uygulanmaz.
- **Kaynaklar arası doğrulama:** TradingView çapraz-kesit verileri ile mali tablodan türetilen TTM metrikler arasında önemli ayrışmalar raporda belirtilir.
- **Veri güven skoru:** eksik/çelişkili veriler kesin yorum üretmek yerine güven uyarısıyla sunulur.
- **Gerçek BIST100 bileşenleri:** BorsaPy Index bileşenleri önceliklidir; fallback kaynak bulunur.
- **Sektör endeksi relatif performansı:** uygun profillerde XBANK, XUTEK, XHOLD, XSGRT, XGMYO vb. endekslere karşı 3A/6A/12A relatif fiyat davranışı hesaplanır.
- **Regresyon smoke testleri:** ASELS (sanayi/savunma) ve AKBNK (banka/UFRS) otomatik test edilir.

## Sonraki geliştirme alanları

- GYO için gerçek NAD/iskonto motoru
- Holdingler için iştirak/NAD bazlı özel değerleme
- Sigorta şirketleri için prim üretimi, teknik kârlılık ve sermaye yeterliliği odaklı özel motor
- Şirketin kendi 5 yıllık değerleme bandı ve tarihsel çarpan yüzdelikleri
- Sektör sıralama/tarama komutları
- Telegram `/analiz ASELS`
- Teknik + temel + relatif güç birleşik araştırma motoru
